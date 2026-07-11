import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ramsey import db
from ramsey.cache import get_redis
from ramsey.models import APIDeleteMovie, APISaveMovie, APIUpdateMovie, SearchQuery
from ramsey.parsing import search_query
from ramsey.settings import get_settings

settings = get_settings()

app = FastAPI()

# Initialize jinja templating engine
cwd = Path(__file__).parent
template_path = cwd.joinpath("templates")
templates = Jinja2Templates(template_path)

# Start serving static files
static_path = cwd.joinpath("static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Initialize redis connection
redis = get_redis()


def format_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%b %d, %Y")


@app.get("/")
async def home(request: Request):
    """Show index page."""

    # Get all watched movies with their watch dates and display them
    watched = []
    for movie in db.get_watched():
        dates = movie.pop("watch_dates")
        movie["times_watched"] = len(dates)
        movie["first_watched"] = format_date(dates[0]) if dates else None
        movie["rewatches"] = [format_date(date) for date in dates[1:]]
        watched.append(movie)

    context = {"watched": watched, "in_index": True}

    return templates.TemplateResponse(request, "index.html", context)


@app.post("/search")
async def search(request: Request, query: SearchQuery):
    """Search for movies and shows with the given query."""

    term = query.search.strip()

    # Quickly respond with an empty component if no query was given
    if term == "":
        context = {"results": []}
        render = templates.TemplateResponse(
            request,
            "components/search_results.html",
            context,
        )
        return render

    # Check if the query results are cached
    cached = redis.get(f"{settings.redis.search_prefix}:{term}")
    if cached:
        results = json.loads(cached)
    else:
        # Parse results and store them in cache
        results = search_query(term)

        ttl = settings.redis.search_ttl
        redis.set(f"{settings.redis.search_prefix}:{term}", json.dumps(results), ex=ttl)

        # Also cache each movie by ID, so it can be saved later
        for movie in results:
            key = f"{settings.redis.movie_prefix}:{movie['id']}"
            redis.set(key, json.dumps(movie), ex=ttl)

    context = {"results": results}
    render = templates.TemplateResponse(
        request,
        "components/search_results.html",
        context,
    )

    return render


@app.post("/api/save-movie")
async def api_save_movie(movie: APISaveMovie):
    """Store a watched movie with its first watch date."""

    # Saving an already stored movie counts as a rewatch
    if db.get_movie(movie.identifier) is not None:
        db.add_watch(movie.identifier)
        return {"status": 200, "message": "OK"}

    # Get the movie data from the cached search results
    cached = redis.get(f"{settings.redis.movie_prefix}:{movie.identifier}")
    if cached is None:
        raise HTTPException(404, "Movie not found in recent search results")

    db.insert_movie(json.loads(cached))
    db.add_watch(movie.identifier)

    return {"status": 200, "message": "OK"}


@app.patch("/api/update-movie")
async def api_update_movie(movie: APIUpdateMovie):
    """Record a rewatch, or undo the most recent one."""

    if db.get_movie(movie.identifier) is None:
        raise HTTPException(404, "Movie not found")

    if movie.action == "inc":
        db.add_watch(movie.identifier)
    elif movie.action == "dec":
        # The first watch can only be removed by deleting the movie
        db.remove_latest_watch(movie.identifier)
    else:
        raise HTTPException(400, f"Unknown action: {movie.action}")

    new_amount = db.count_watches(movie.identifier)

    response = {
        "status": 200,
        "message": "OK",
        "data": {"new_amount": new_amount},
    }

    return response


@app.delete("/api/delete-movie")
async def api_delete_movie(movie: APIDeleteMovie):
    """Delete a movie and its watch history."""

    if db.get_movie(movie.identifier) is None:
        raise HTTPException(404, "Movie not found")

    db.delete_movie(movie.identifier)

    return {"status": 200, "message": "OK"}
