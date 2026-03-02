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
template_dirs = [
    str(BASE_DIR / "templates"),
    str(BASE_DIR / "dms" / "templates")
]
templates = Jinja2Templates(directory=template_dirs)

# Helpers for Jinja2 Templates (To make it feel like Django)
def get_static_url(path: str) -> str:
    return f"/static/{path}"

def dummy_url(name: str, *args, **kwargs) -> str:
    # Later we will implement a real URL reverter
    arg_str = "/".join([str(a) for a in args])
    kw_str = "/".join([f"{k}={v}" for k, v in kwargs.items()])
    return f"/{name}/{arg_str}/{kw_str}".strip("/")

def yesno(value, arg):
    """
    Simulate Django's yesno filter
    """
    bits = arg.split(',')
    if len(bits) < 2:
        return value
    try:
        yes, no = bits[0], bits[1]
        maybe = bits[2] if len(bits) > 2 else no
    except IndexError:
        return value
        
    if value is True: return yes
    if value is False: return no
    return maybe

def translate(text):
    return text

templates.env.globals.update(
    static=get_static_url, 
    url=dummy_url,
    csrf_token=lambda: "", # Dummy for now
    translate=translate,
)
templates.env.filters["yesno"] = yesno
templates.env.filters["translate"] = translate

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
