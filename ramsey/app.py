from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    context = {}
    response = templates.TemplateResponse(request, "index.html", context)
    return response
