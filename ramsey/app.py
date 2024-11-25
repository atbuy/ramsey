import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ramsey.cache import get_redis
from ramsey.models import SearchQuery
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


@app.get("/")
async def home(request: Request):
    """Show index page."""

    return templates.TemplateResponse(request, "index.html")


@app.post("/search")
async def search(request: Request, query: SearchQuery):
    """Search for movies and shows with the given query."""

    # Quickly respond with an empty component if no query was given
    if query.search.strip() == "":
        context = {"results": []}
        render = templates.TemplateResponse(
            request,
            "components/search_results.html",
            context,
        )
        return render

    # Check if there are data cached
    cached = redis.get(settings.redis.data_key) or "{}"
    data = json.loads(cached)
    if not data:
        # Parse results and render the template with the data
        results = search_query(query.search)

        # Store result data in cache
        data[query.search] = results
        redis.set(settings.redis.data_key, json.dumps(data))
    else:
        results = data[query.search]

    context = {"results": results}
    render = templates.TemplateResponse(
        request,
        "components/search_results.html",
        context,
    )

    return render
