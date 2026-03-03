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
def smart_url_for(name: str, *args, **kwargs):
    """
    Wrapper for app.url_path_for that handles positional arguments by mapping them 
    to path parameters in the route's definition.
    """
    try:
        import re
        for route in app.routes:
            if hasattr(route, "name") and route.name == name:
                # Find all {param} in the route path
                params = re.findall(r'\{([a-zA-Z_0-9]+)\}', route.path)
                for i, arg in enumerate(args):
                    if i < len(params):
                        param_name = params[i]
                        if param_name not in kwargs:
                            kwargs[param_name] = str(arg)
                break
        return app.url_path_for(name, **kwargs)
    except Exception as e:
        # If route not found or other error, fallback to original or return error string
        # To help debugging, we can return the error, but for production # is safer
        print(f"Error resolving URL for {name} with args {args}: {e}")
        return "#"

templates.env.globals["url"] = smart_url_for
templates.env.globals["static"] = lambda path: app.url_path_for("static", path=path)

# Custom Filters for Template Compatibility
def add_filter(value, arg):
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value

def stringformat_filter(value, arg):
    try:
        if arg == "s": return str(value)
        return ("%" + arg) % value
    except:
        return value

def truncatechars_filter(value, arg):
    try:
        length = int(arg)
        if len(str(value)) > length:
            return str(value)[:length] + "..."
        return value
    except:
        return value

templates.env.filters["add"] = add_filter
templates.env.filters["int"] = lambda v: int(v) if v is not None else 0
templates.env.filters["stringformat"] = stringformat_filter
templates.env.filters["truncatechars"] = truncatechars_filter
templates.env.filters["cut"] = lambda v, arg: str(v).replace(arg, "")
templates.env.filters["time"] = lambda v, arg: v.strftime(arg) if hasattr(v, "strftime") else v
templates.env.filters["dict_key"] = lambda d, k: d.get(k) if isinstance(d, dict) else None

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
    return await TemplateResponse.render("404.html", request, None, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    import traceback
    print("\n" + "="*50)
    print("CRITICAL SERVER ERROR DETECTED:")
    print("="*50)
    traceback.print_exc()
    print("="*50 + "\n")
    
    try:
        # Try to render the pretty 500 page
        return await TemplateResponse.render("500.html", request, None, status_code=500, context={"error": str(exc)})
    except Exception as render_exc:
        # Fallback if 500.html ALSO has a syntax error
        print(f"ERROR: Fallback rendering failed: {render_exc}")
        return HTMLResponse(
            content=f"<html><body><h1>500 Internal Server Error</h1><p>Original Error: {exc}</p><p>Template Error: {render_exc}</p></body></html>",
            status_code=500
        )
