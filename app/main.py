from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
import traceback
import logging
from logging.handlers import RotatingFileHandler
from sqlmodel import Session

from app.core.config import settings
from app.core.database import get_session
from app.utils.context import get_global_context
from app.logic.auth import get_current_user

# API Routers
from app.api import (
    auth_router, base_router, student_router, staff_router,
    finance_router, audit_router, attendance_router, export_router,
    course_router, facility_router, inventory_router, schedule_router,
    public_admission_router, exams_router,
    guardian_router, global_router, notification_router
)
from app.admin import setup_admin

from contextlib import asynccontextmanager
from app.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    init_db()
    yield
    # Shutdown logic

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

# ── Production Proxy Fix ────────────────────────────────────────
# جب PRODUCTION_HOST سیٹ ہو تو Host header اور scheme درست کریں
# تاکہ admin redirect 127.0.0.1:8001 کی بجائے اصل domain پر جائے
if settings.PRODUCTION_HOST:
    from starlette.types import ASGIApp, Receive, Scope, Send

    class RealHostMiddleware:
        def __init__(self, app: ASGIApp):
            self.app = app
            self._host = settings.PRODUCTION_HOST.encode()

        async def __call__(self, scope: Scope, receive: Receive, send: Send):
            if scope["type"] in ("http", "websocket"):
                scope["scheme"] = "https"
                scope["server"] = (settings.PRODUCTION_HOST, 443)
                headers = [
                    (k, v) for k, v in scope.get("headers", [])
                    if k not in (b"host", b"x-forwarded-host", b"x-forwarded-proto")
                ]
                headers += [
                    (b"host", self._host),
                    (b"x-forwarded-host", self._host),
                    (b"x-forwarded-proto", b"https"),
                ]
                scope["headers"] = headers
            await self.app(scope, receive, send)

    app.add_middleware(RealHostMiddleware)

# ProxyHeadersMiddleware صرف uvicorn پر چلتا ہے، Passenger/WSGI پر نہیں
# یہ Passenger کے ساتھ signal: 15 کریش کو روکتا ہے
if not os.environ.get("PASSENGER_BASE_URI"):
    try:
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    except ImportError:
        pass


# --- Enhanced Logging Configuration ---
LOG_FILE = "debug.log"
UVICORN_LOG_FILE = "uvicorn.log"
log_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

# Rotating file handler — App errors → debug.log (10MB, 5 backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Stream handler for terminal
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)

# App logger → debug.log
app_logger = logging.getLogger("dms_app")
app_logger.setLevel(logging.INFO)
app_logger.addHandler(file_handler)
app_logger.addHandler(stream_handler)
app_logger.propagate = False

# ── Uvicorn errors → uvicorn.log (الگ file) ───────────────
# startup fail, port busy, worker crash — uvicorn.log میں
uvicorn_file_handler = RotatingFileHandler(
    UVICORN_LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
uvicorn_file_handler.setFormatter(log_formatter)
uvicorn_file_handler.setLevel(logging.WARNING)  # صرف warnings اور errors

for _name in ("uvicorn", "uvicorn.error"):
    _logger = logging.getLogger(_name)
    _logger.addHandler(uvicorn_file_handler)
    _logger.propagate = True  # terminal پر بھی دکھائیں

# --- Error & Request Logging ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs requests that result in errors, and catches any underlying unhandled crashes."""
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            app_logger.warning(f"HTTP {response.status_code} | {request.method} {request.url.path}")
        return response
    except Exception as exc:
        error_trace = traceback.format_exc()
        app_logger.critical(f"\n{'X'*60}\n❌ CRITICAL MIDDLEWARE CRASH\nURL: {request.url}\nMethod: {request.method}\nTraceback:\n{error_trace}\n{'X'*60}")
        raise exc # Re-raise to let the global exception handler deal with the final response

@app.post("/log-client-error")
async def log_client_error(request: Request):
    """Receives and prints browser console errors to log file and terminal"""
    try:
        data = await request.json()
        error_msg = (
            f"\n" + "!"*60 + "\n"
            f"🌐 BROWSER ERROR CAPTURED:\n"
            f"Message : {data.get('message')}\n"
            f"Source  : {data.get('source')} (Line: {data.get('lineno')}, Col: {data.get('colno')})\n"
            f"Location: {data.get('url')}\n"
            f"Stack Trace:\n{data.get('stack')}\n"
            + "!"*60
        )
        app_logger.error(error_msg)
    except Exception as e:
        app_logger.error(f"Error logging client error: {e}")
    return {"status": "logged"}
# -------------------------------

# Mount Static Files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

from app.utils.context import templates, TemplateResponse

# Configure Templates Globals
def smart_url_for(name: str, *args, **kwargs):
    """
    Wrapper for app.url_path_for that handles positional arguments and query parameters.
    """
    try:
        import re
        from urllib.parse import urlencode
        
        route_path = ""
        path_params = []
        for route in app.routes:
            if hasattr(route, "name") and route.name == name:
                route_path = route.path
                path_params = re.findall(r'\{([a-zA-Z_0-9]+)\}', route_path)
                break
        
        if not route_path:
            return app.url_path_for(name, **kwargs)
            
        # 1. Map positional args to path params
        for i, arg in enumerate(args):
            if i < len(path_params):
                kw = path_params[i]
                if kw not in kwargs:
                    kwargs[kw] = str(arg)
        
        # 2. Separate path kwargs from query kwargs
        path_kwargs = {}
        query_kwargs = {}
        for k, v in kwargs.items():
            if k in path_params:
                path_kwargs[k] = v
            else:
                query_kwargs[k] = v
        
        url = app.url_path_for(name, **path_kwargs)
        if query_kwargs:
            url = f"{url}?{urlencode(query_kwargs)}"
        return url
    except Exception as e:
        print(f"Error resolving URL for {name}: {e}")
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
templates.env.filters["time"] = lambda v, arg="%H:%M": v.strftime(arg) if hasattr(v, "strftime") else v
templates.env.filters["dict_key"] = lambda d, k: d.get(k) if isinstance(d, dict) else None

# Setup SQLAdmin — routers سے پہلے mount کریں
# (تاکہ /{slug}/ route /dms-admin/ کو نہ پکڑے)
admin = setup_admin(app)

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
app.include_router(public_admission_router, tags=["Public Admission"])
app.include_router(exams_router, tags=["Exams"])
app.include_router(guardian_router, tags=["Parent Portal"])
app.include_router(global_router, tags=["Global Overview"])
app.include_router(notification_router, tags=["Notifications"])

# Global Exception Handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return await TemplateResponse.render("404.html", request, None, status_code=404)

@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    detail = getattr(exc, "detail", "آپ کو اس صفحے تک رسائی کی اجازت نہیں۔")
    return await TemplateResponse.render("403.html", request, None, {"detail": detail}, status_code=403)

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc: HTTPException):
    """صارف لاگ ان نہیں ہے، لاگ ان پیج پر ری ڈائریکٹ کریں۔"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login/", status_code=303)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    error_msg = (
        f"\n" + "X"*60 + "\n"
        f"❌ UNHANDLED FATAL SERVER ERROR DETECTED:\n"
        f"URL: {request.url}\n"
        f"Method: {request.method}\n"
        f"Error: {repr(exc)}\n"
        f"Traceback:\n{error_trace}\n"
        + "X"*60
    )
    app_logger.critical(error_msg)
    
    try:
        # Try to render the pretty 500 page
        return await TemplateResponse.render("500.html", request, None, {"error": str(exc)}, status_code=500)
    except Exception as render_exc:
        # Fallback if 500.html ALSO has a syntax error
        print(f"ERROR: Fallback rendering failed: {render_exc}")
        return HTMLResponse(
            content=f"<html><body style='background:#111;color:#f87171;padding:2rem;font-family:sans-serif;'><h1>500 Internal Server Error</h1><p>Original Error: {exc}</p><p>Template Error: {render_exc}</p></body></html>",
            status_code=500
        )
