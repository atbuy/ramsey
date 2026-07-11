import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ramsey import db
from ramsey.cache import get_redis
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


@lru_cache(maxsize=None)
def static_url(path: str) -> str:
    """Build a static file URL with a content hash to bust browser caches."""

    digest = hashlib.md5(static_path.joinpath(path).read_bytes()).hexdigest()[:8]
    return f"/static/{path}?v={digest}"


templates.env.globals["static_url"] = static_url

# Initialize redis connection
redis = get_redis()


def format_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%b %d, %Y")


def get_watched() -> list[dict]:
    """Get all watched movies with their formatted watch dates."""

    watched = []
    for movie in db.get_watched():
        dates = movie.pop("watch_dates")
        movie["times_watched"] = len(dates)
        movie["first_watched"] = format_date(dates[0]) if dates else None
        movie["rewatches"] = [format_date(date) for date in dates[1:]]
        watched.append(movie)

    return watched


def render_watched(request: Request):
    """Render the watched list fragment, swapped in after every change."""

    context = {"watched": get_watched()}
    return templates.TemplateResponse(request, "components/watched.html", context)


@app.get("/")
async def home(request: Request):
    """Show index page."""

    context = {"watched": get_watched()}

    return templates.TemplateResponse(request, "index.html", context)


@app.get("/search")
async def search(request: Request, search: str = ""):
    """Search for movies and shows with the given query."""

    term = search.strip()
    results = []

    if term:
        # Check if the query results are cached
        cached = redis.get(f"{settings.redis.search_prefix}:{term}")
        if cached:
            results = json.loads(cached)
        else:
            # Parse results and store them in cache
            results = search_query(term)

            ttl = settings.redis.search_ttl
            key = f"{settings.redis.search_prefix}:{term}"
            redis.set(key, json.dumps(results), ex=ttl)

            # Also cache each movie by ID, so it can be saved later
            for movie in results:
                key = f"{settings.redis.movie_prefix}:{movie['id']}"
                redis.set(key, json.dumps(movie), ex=ttl)

    context = {"results": results, "term": term, "saved": db.get_saved_ids()}
    render = templates.TemplateResponse(
        request,
        "components/search_results.html",
        context,
    )

    return render


@app.post("/movies/{movie_id}")
async def save_movie(request: Request, movie_id: str):
    """Store a watched movie, or record a rewatch if it is already stored."""

    if db.get_movie(movie_id) is not None:
        db.add_watch(movie_id)
        return render_watched(request)

    # Get the movie data from the cached search results
    cached = redis.get(f"{settings.redis.movie_prefix}:{movie_id}")
    if cached is None:
        raise HTTPException(404, "Movie not found in recent search results")

    db.insert_movie(json.loads(cached))
    db.add_watch(movie_id)

    return render_watched(request)


@app.post("/movies/{movie_id}/watch")
async def watch_movie(request: Request, movie_id: str):
    """Record a rewatch."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.add_watch(movie_id)

    return render_watched(request)


@app.delete("/movies/{movie_id}/watch")
async def unwatch_movie(request: Request, movie_id: str):
    """Undo the most recent rewatch, always keeping the first watch."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.remove_latest_watch(movie_id)

    return render_watched(request)


@app.put("/movies/{movie_id}/rating/{rating}")
async def rate_movie(request: Request, movie_id: str, rating: int):
    """Rate a movie from 1 to 10."""

    if not 1 <= rating <= 10:
        raise HTTPException(400, "Rating must be between 1 and 10")

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.set_rating(movie_id, rating)

    return render_watched(request)


@app.delete("/movies/{movie_id}/rating")
async def unrate_movie(request: Request, movie_id: str):
    """Clear the rating of a movie."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.set_rating(movie_id, None)

    return render_watched(request)


@app.delete("/movies/{movie_id}")
async def remove_movie(request: Request, movie_id: str):
    """Delete a movie and its watch history."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.delete_movie(movie_id)

    return render_watched(request)
