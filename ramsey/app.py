import csv
import hashlib
import io
import json
import random
from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
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

# Human labels for the title types of the suggestion API
TYPE_LABELS = {
    "movie": "Movie",
    "tvSeries": "Series",
    "tvMiniSeries": "Mini-series",
    "tvMovie": "TV movie",
    "tvSpecial": "TV special",
    "short": "Short",
    "video": "Video",
    "musicVideo": "Music video",
    "videoGame": "Game",
}
templates.env.globals["kind"] = TYPE_LABELS.get

TYPE_FILTERS = ("all", "movies", "shows")
SORTS = ("watched", "rating", "times", "title")

# Initialize redis connection
redis = get_redis()


def format_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%b %d, %Y")


def library_prefs(request: Request) -> tuple[str, str]:
    """Get the active library filter and sort, from the query or cookies."""

    type_filter = request.query_params.get("type") or request.cookies.get(
        "library-type"
    )
    sort = request.query_params.get("sort") or request.cookies.get("library-sort")

    if type_filter not in TYPE_FILTERS:
        type_filter = "all"
    if sort not in SORTS:
        sort = "watched"

    return type_filter, sort


def matches_filter(movie: dict, type_filter: str) -> bool:
    if type_filter == "movies":
        return movie["type"] == "movie"
    if type_filter == "shows":
        return str(movie["type"] or "").startswith("tv")
    return True


def library_context(request: Request) -> dict:
    """Split all movies into the watched list and the watchlist."""

    type_filter, sort = library_prefs(request)

    watched = []
    watchlist = []
    for movie in db.get_movies():
        if not matches_filter(movie, type_filter):
            continue

        dates = movie.pop("watch_dates")
        movie["times_watched"] = len(dates)
        if dates:
            movie["first_watched"] = format_date(dates[0])
            movie["rewatches"] = [format_date(date) for date in dates[1:]]
            watched.append(movie)
        else:
            movie["added"] = format_date(movie["added_at"])
            watchlist.append(movie)

    # The default "watched" order comes sorted from the database already
    if sort == "rating":
        watched.sort(key=lambda movie: movie["rating"] or 0, reverse=True)
    elif sort == "times":
        watched.sort(key=lambda movie: movie["times_watched"], reverse=True)
    elif sort == "title":
        watched.sort(key=lambda movie: movie["title"].lower())

    return {
        "watched": watched,
        "watchlist": watchlist,
        "type_filter": type_filter,
        "sort": sort,
    }


def render_library(request: Request, oob: bool = False) -> str:
    """Render the library fragment, swapped in after every change."""

    context = library_context(request) | {"oob": oob}
    return templates.get_template("components/library.html").render(context)


def render_detail(movie_id: str, pick: bool = False) -> str:
    """Render the detail view of a single movie."""

    movie = dict(db.get_movie(movie_id))
    movie["watches"] = [
        {"id": watch["id"], "date": format_date(watch["watched_at"])}
        for watch in db.get_watches(movie_id)
    ]

    return templates.get_template("components/movie_detail.html").render(
        {"movie": movie, "pick": pick}
    )


def respond(
    request: Request,
    movie_id: str | None = None,
    toast: str | None = None,
):
    """Render the fragments htmx expects, based on the triggering element.

    Changes made from the detail view get an updated detail fragment plus
    the library as an out-of-band swap; everything else gets the library.
    A toast message is delivered through the HX-Trigger response header.
    """

    if request.headers.get("hx-target") == "modal":
        detail = ""
        if movie_id and db.get_movie(movie_id) is not None:
            detail = render_detail(movie_id)
        response = HTMLResponse(detail + render_library(request, oob=True))
    else:
        response = HTMLResponse(render_library(request))

    if toast:
        response.headers["HX-Trigger"] = json.dumps({"ramsey:toast": toast})

    return response


def watch_removed_toast(movie_id: str) -> str:
    """Describe a removed watch, noting when the movie leaves the watched list."""

    movie = db.get_movie(movie_id)
    if not db.get_watches(movie_id):
        return f"Moved {movie['title']} to the watchlist"

    return f"Watch removed: {movie['title']}"


def month_buckets(count: int = 12) -> list[tuple[int, int]]:
    """Get the last months as (year, month) pairs, oldest first."""

    now = datetime.now()
    year, month = now.year, now.month

    buckets = []
    for _ in range(count):
        buckets.append((year, month))
        month -= 1
        if month == 0:
            year -= 1
            month = 12

    return buckets[::-1]


def stats_context() -> dict:
    """Aggregate the library into the numbers shown on the stats page."""

    movies = db.get_movies()
    watched = [movie for movie in movies if movie["watch_dates"]]
    ratings = [movie["rating"] for movie in movies if movie["rating"]]

    # Watch events bucketed into the last 12 months
    counts: Counter = Counter()
    for timestamp in db.get_watch_times():
        moment = datetime.fromtimestamp(timestamp)
        counts[(moment.year, moment.month)] += 1

    months = []
    for year, month in month_buckets():
        date = datetime(year, month, 1)
        months.append(
            {
                "tick": date.strftime("%b"),
                "label": date.strftime("%b %Y"),
                "count": counts[(year, month)],
            }
        )

    # How the given ratings are distributed
    histogram = Counter(ratings)
    rated = [
        {"tick": rating, "label": f"Rated {rating}/10", "count": histogram[rating]}
        for rating in range(1, 11)
    ]

    for items in (months, rated):
        top = max(item["count"] for item in items)
        for item in items:
            item["pct"] = item["count"] / top * 100 if top else 0

    rewatched = sorted(
        (movie for movie in watched if len(movie["watch_dates"]) > 1),
        key=lambda movie: len(movie["watch_dates"]),
        reverse=True,
    )

    average = round(sum(ratings) / len(ratings), 1) if ratings else None

    return {
        "watched_count": len(watched),
        "watchlist_count": len(movies) - len(watched),
        "total_watches": sum(len(movie["watch_dates"]) for movie in movies),
        "average_rating": average,
        "rated_count": len(ratings),
        "months": {"items": months, "max": max(m["count"] for m in months)},
        "ratings": {"items": rated, "max": max(r["count"] for r in rated)},
        "most_rewatched": [
            {
                "id": movie["id"],
                "title": movie["title"],
                "image": movie["image"],
                "count": len(movie["watch_dates"]),
            }
            for movie in rewatched[:3]
        ],
    }


@app.get("/")
async def home(request: Request):
    """Show index page."""

    return templates.TemplateResponse(request, "index.html", library_context(request))


@app.get("/library")
async def library(request: Request):
    """Render the library with the given filter and sort, and remember them."""

    type_filter, sort = library_prefs(request)

    response = HTMLResponse(render_library(request))
    response.set_cookie("library-type", type_filter, max_age=60 * 60 * 24 * 365)
    response.set_cookie("library-sort", sort, max_age=60 * 60 * 24 * 365)

    return response


@app.get("/stats")
async def stats(request: Request):
    """Show statistics about the watched movies."""

    return templates.TemplateResponse(request, "stats.html", stats_context())


def iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def export_movies() -> list[dict]:
    """Collect the whole library with readable dates for exporting."""

    out = []
    for movie in db.get_movies():
        out.append(
            {
                "id": movie["id"],
                "title": movie["title"],
                "year": movie["year"],
                "people": movie["people"],
                "rating": movie["rating"],
                "notes": movie["notes"],
                "image": movie["image"],
                "added_at": iso(movie["added_at"]),
                "watches": [iso(date) for date in movie["watch_dates"]],
            }
        )

    return out


def export_response(content: str, media_type: str, extension: str) -> Response:
    """Build a download response for an export."""

    filename = f"ramsey-export-{datetime.now():%Y-%m-%d}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/json")
async def export_json():
    """Download the library as JSON."""

    data = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "movies": export_movies(),
    }
    content = json.dumps(data, indent=2, ensure_ascii=False)

    return export_response(content, "application/json", "json")


@app.get("/export/csv")
async def export_csv():
    """Download the library as CSV, one row per movie."""

    columns = [
        "id",
        "title",
        "year",
        "people",
        "rating",
        "notes",
        "image",
        "added_at",
        "watches",
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for movie in export_movies():
        movie["watches"] = ";".join(movie["watches"])
        writer.writerow(movie[column] for column in columns)

    return export_response(buffer.getvalue(), "text/csv", "csv")


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

    watched_ids = db.get_watched_ids()
    context = {
        "results": results,
        "term": term,
        "watched_ids": watched_ids,
        "watchlist_ids": db.get_saved_ids() - watched_ids,
    }
    render = templates.TemplateResponse(
        request,
        "components/search_results.html",
        context,
    )

    return render


def save_from_search(movie_id: str) -> None:
    """Store a movie using the data cached by a recent search."""

    cached = redis.get(f"{settings.redis.movie_prefix}:{movie_id}")
    if cached is None:
        raise HTTPException(404, "Movie not found in recent search results")

    db.insert_movie(json.loads(cached))


@app.get("/movies/{movie_id}")
async def movie_detail(movie_id: str):
    """Show the detail view of a movie."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    return HTMLResponse(render_detail(movie_id))


@app.post("/movies/{movie_id}")
async def save_movie(request: Request, movie_id: str):
    """Store a watched movie, or record a rewatch if it is already stored."""

    existing = db.get_movie(movie_id)
    if existing is None:
        save_from_search(movie_id)

    db.add_watch(movie_id)

    title = db.get_movie(movie_id)["title"]
    toast = f"Rewatch logged: {title}" if existing else f"Added {title}"

    return respond(request, movie_id, toast)


@app.get("/watchlist/pick")
async def pick_from_watchlist(request: Request):
    """Open a random movie from the watchlist, respecting the active filter."""

    type_filter, _ = library_prefs(request)
    candidates = [
        movie
        for movie in db.get_movies()
        if not movie["watch_dates"] and matches_filter(movie, type_filter)
    ]

    if not candidates:
        raise HTTPException(404, "The watchlist is empty")

    choice = random.choice(candidates)

    return HTMLResponse(render_detail(choice["id"], pick=True))


@app.post("/watchlist/{movie_id}")
async def add_to_watchlist(request: Request, movie_id: str):
    """Store a movie to watch later, without a watch date."""

    toast = None
    if db.get_movie(movie_id) is None:
        save_from_search(movie_id)
        toast = f"Added {db.get_movie(movie_id)['title']} to the watchlist"

    return respond(request, movie_id, toast)


@app.post("/movies/{movie_id}/watch")
async def watch_movie(request: Request, movie_id: str):
    """Record a watch, optionally on a past date."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    form = await request.form()
    watched_on = str(form.get("watched_on") or "")

    watched_at = None
    if watched_on:
        try:
            watched_at = datetime.strptime(watched_on, "%Y-%m-%d").timestamp()
        except ValueError:
            raise HTTPException(400, "Invalid date") from None

    db.add_watch(movie_id, watched_at)

    toast = f"Watch logged: {db.get_movie(movie_id)['title']}"
    if watched_at:
        toast += f" on {format_date(watched_at)}"

    return respond(request, movie_id, toast)


@app.delete("/movies/{movie_id}/watch")
async def unwatch_movie(request: Request, movie_id: str):
    """Undo the most recent watch.

    Removing the last one moves the movie to the watchlist.
    """

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.remove_latest_watch(movie_id)

    return respond(request, movie_id, watch_removed_toast(movie_id))


@app.delete("/watches/{watch_id}")
async def delete_watch(request: Request, watch_id: int):
    """Delete a single watch event from a movie's history."""

    watch = db.get_watch(watch_id)
    if watch is None:
        raise HTTPException(404, "Watch not found")

    db.delete_watch(watch_id)

    return respond(request, watch["movie_id"], watch_removed_toast(watch["movie_id"]))


@app.put("/movies/{movie_id}/notes")
async def update_notes(request: Request, movie_id: str):
    """Set or clear the notes of a movie."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    form = await request.form()
    notes = str(form.get("notes") or "").strip() or None
    db.set_notes(movie_id, notes)

    return respond(request, movie_id, "Notes saved" if notes else "Notes cleared")


@app.put("/movies/{movie_id}/rating/{rating}")
async def rate_movie(request: Request, movie_id: str, rating: int):
    """Rate a movie from 1 to 10."""

    if not 1 <= rating <= 10:
        raise HTTPException(400, "Rating must be between 1 and 10")

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.set_rating(movie_id, rating)

    toast = f"Rated {db.get_movie(movie_id)['title']} {rating}/10"

    return respond(request, movie_id, toast)


@app.delete("/movies/{movie_id}/rating")
async def unrate_movie(request: Request, movie_id: str):
    """Clear the rating of a movie."""

    if db.get_movie(movie_id) is None:
        raise HTTPException(404, "Movie not found")

    db.set_rating(movie_id, None)

    toast = f"Rating cleared: {db.get_movie(movie_id)['title']}"

    return respond(request, movie_id, toast)


@app.delete("/movies/{movie_id}")
async def remove_movie(request: Request, movie_id: str):
    """Delete a movie, its watch history and notes."""

    movie = db.get_movie(movie_id)
    if movie is None:
        raise HTTPException(404, "Movie not found")

    db.delete_movie(movie_id)

    return respond(request, toast=f"Removed {movie['title']}")
