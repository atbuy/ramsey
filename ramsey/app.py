from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ramsey.models import SearchQuery
from ramsey.parsing import search_query

app = FastAPI()

# Initialize jinja templating engine
cwd = Path(__file__).parent
template_path = cwd.joinpath("templates")
templates = Jinja2Templates(template_path)

# Start serving static files
static_path = cwd.joinpath("static")
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def home(request: Request):
    """Show index page."""

    return templates.TemplateResponse(request, "index.html")


@app.post("/search")
async def search(request: Request, query: SearchQuery):
    """Search for movies and shows with the given query."""

    # Parse results and render the template with the data
    results = search_query(query.search)

    context = {"results": results}
    render = templates.TemplateResponse(
        request,
        "components/search_results.html",
        context,
    )

    return render
