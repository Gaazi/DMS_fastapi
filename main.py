import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import AuthenticationBackend, AuthCredentials, UnauthenticatedUser

class MockAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        # Mocking an authenticated superuser
        return AuthCredentials(["authenticated"]), UnauthenticatedUser() # Or a mock user

app = FastAPI(title="DMS FastAPI", description="Data Management System migrated from Django")
app.add_middleware(AuthenticationMiddleware, backend=MockAuthBackend())

# Middleware to mock Django's request.user until Auth system is built
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    # Mock user object
    class MockUser:
        is_authenticated = True
        is_superuser = True
        username = "admin"
        def has_usable_password(self): return True

    request.state.user = MockUser()
    response = await call_next(request)
    return response

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
    # Remove quotes if name comes as a string representation
    name = name.strip("'\"")
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

def short_id(reg_id):
    if not reg_id: return ""
    parts = str(reg_id).split('-')
    return parts[-1] if parts else reg_id

def split_filter(value, arg):
    return value.split(arg) if value else []

def dict_key(d, k):
    return d.get(k) if isinstance(d, dict) else None

templates.env.globals.update(
    static=get_static_url, 
    url=dummy_url,
    csrf_token=lambda: "", # Dummy for now
    translate=translate,
)
templates.env.filters["yesno"] = yesno
templates.env.filters["translate"] = translate
templates.env.filters["short_id"] = short_id
templates.env.filters["split"] = split_filter
templates.env.filters["dict_key"] = dict_key

@app.get("/")
async def home(request: Request):
    """
    Home page rendering index.html with dummy context for Django compatibility
    """
    context = {
        "request": request,
        "user": request.state.user,
        "title": "DMS FastAPI Home",
        "dms_header": {
            "unread_count": 0,
            "notifications_json": "[]",
            "user": {"name": "Admin", "initials": "AD", "role": "Administrator"},
            "all_institutions": []
        },
        "current_institution": None,
        "is_dms_admin": True,
    }
    try:
        return templates.TemplateResponse("index.html", context)
    except Exception as e:
        return {"error": "Template not found or error rendering", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
