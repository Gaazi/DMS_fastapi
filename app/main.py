from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.helper.context import get_global_context
from app.logic.auth import get_current_user

# API Routers
from .api import (
    auth_router, base_router, student_router, staff_router,
    finance_router, audit_router, attendance_router, export_router,
    course_router, facility_router, inventory_router, schedule_router,
    finance_extra_router, public_admission_router, exams_router,
    guardian_router, global_router
)
from .admin import setup_admin

from contextlib import asynccontextmanager
from app.db.session import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    yield
    # Shutdown logic

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# Mount Static Files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

from app.helper.context import templates, TemplateResponse

# Configure Templates Globals
templates.env.globals["url"] = app.url_path_for
templates.env.globals["static"] = lambda path: app.url_path_for("static", path=path)

# Register Routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(base_router, tags=["General"])
app.include_router(student_router, tags=["Students"])
app.include_router(staff_router, tags=["Staff"])
app.include_router(finance_router, tags=["Finance"])
app.include_router(audit_router, tags=["Audit"])
app.include_router(attendance_router, tags=["Attendance"])
app.include_router(export_router, tags=["Export"])
app.include_router(course_router, tags=["Courses"])
app.include_router(facility_router, tags=["Facilities"])
app.include_router(inventory_router, tags=["Inventory"])
app.include_router(schedule_router, tags=["Schedule"])
app.include_router(finance_extra_router, tags=["Finance Extra"])
app.include_router(public_admission_router, tags=["Public Admission"])
app.include_router(exams_router, tags=["Exams"])
app.include_router(guardian_router, tags=["Parent Portal"])
app.include_router(global_router, tags=["Global Overview"])

# Setup SQLAdmin
admin = setup_admin(app)

# Global Exception Handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
