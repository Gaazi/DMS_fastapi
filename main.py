import os
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import AuthenticationBackend, AuthCredentials
from database import engine, get_session
from sqlalchemy.orm import Session
from models import Institution
from templating import templates
from routers import core, students, staff, finance, institutions

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

class MockUser:
    is_authenticated = True
    is_superuser = True
    username = "admin"
    name = "Admin"
    initials = "AD"
    role = "Administrator"
    id = 1
    def has_usable_password(self): return True
    @property
    def institution_set(self):
        class MockSet:
            def all(self): return []
            def first(self): return None
        return MockSet()

class MockAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        return AuthCredentials(["authenticated"]), MockUser()

app = FastAPI(title="DMS FastAPI", description="Data Management System migrated from Django")
app.add_middleware(AuthenticationMiddleware, backend=MockAuthBackend())

# Mock user in request state
@app.middleware("http")
async def add_user_to_state(request: Request, call_next):
    request.state.user = MockUser()
# Static and Media Files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
if (BASE_DIR / "media").exists():
    app.mount("/media", StaticFiles(directory=str(BASE_DIR / "media")), name="media")

# Include Routers
app.include_router(core.router)
app.include_router(institutions.router)
app.include_router(students.router)
app.include_router(staff.router)
app.include_router(finance.router)

# Home route (if not in core)
@app.get("/logout", name="dms_logout")
async def logout():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
