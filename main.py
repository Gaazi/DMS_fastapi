import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="DMS FastAPI", description="Data Management System migrated from Django")

# Helpers for Jinja2 Templates (To make it feel like Django)
def get_static_url(path: str) -> str:
    return f"/static/{path}"

# Static & Media Files Setup
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR / "media"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Templates Setup
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Helpers for Jinja2 Templates (To make it feel like Django)
def get_static_url(path: str) -> str:
    return f"/static/{path}"

def dummy_url(name: str, **kwargs) -> str:
    # Later we will implement a real URL reverter
    return f"/{name}"

templates.env.globals.update(static=get_static_url, url=dummy_url)

@app.get("/")
async def home(request: Request):
    """
    Home page rendering index.html
    """
    try:
        return templates.TemplateResponse("index.html", {"request": request, "title": "DMS FastAPI Home"})
    except Exception as e:
        return {"error": "Template not found or error rendering", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
