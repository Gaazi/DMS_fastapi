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

# Static Files Setup
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Media Files Setup (if needed)
if (BASE_DIR / "media").exists():
    app.mount("/media", StaticFiles(directory=str(BASE_DIR / "media")), name="media")

# Templates Setup
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/")
async def home(request: Request):
    # Abhi ke liye sirf ek welcome message, kyunki templates ko migrate karna baqi hai
    return templates.TemplateResponse("index.html", {"request": request, "title": "DMS FastAPI Home"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
