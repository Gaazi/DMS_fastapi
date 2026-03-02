import os
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

template_dirs = [
    str(BASE_DIR / "templates"),
    str(BASE_DIR / "dms" / "templates")
]

templates = Jinja2Templates(directory=template_dirs)

# Helpers for Jinja2 Templates
def get_static_url(path: str) -> str:
    return f"/static/{path}"

def dummy_url(name: str, *args, **kwargs) -> str:
    name = name.strip("'\"")
    # This will be overridden or used carefully. 
    # In FastAPI, we usually use request.url_for
    return f"/{name}" # Placeholder

def yesno(value, arg):
    bits = arg.split(',')
    if len(bits) < 2: return value
    try:
        yes, no = bits[0], bits[1]
        maybe = bits[2] if len(bits) > 2 else no
    except IndexError: return value
    if value is True: return yes
    if value is False: return no
    return maybe

def translate(text): return text

def short_id(reg_id):
    if not reg_id: return ""
    parts = str(reg_id).split('-')
    return parts[-1] if parts else reg_id

def split_filter(value, arg):
    return value.split(arg) if value else []

def dict_key(d, k):
    return d.get(k) if isinstance(d, dict) else None

def django_now(format_string):
    return datetime.now().strftime(format_string.replace('Y', '%Y').replace('m', '%m').replace('d', '%d'))

# Initialize globals and filters
templates.env.globals.update(
    static=get_static_url,
    translate=translate,
    now=django_now,
)

from models import Institution
from sqlalchemy.orm import Session
from database import get_session

def render_template(template_name: str, request, context: dict, session: Session):
    base_context = {
        "request": request,
        "user": getattr(request.state, 'user', None),
        "dms_header": {
            "unread_count": 0,
            "notifications_json": [],
            "user": getattr(request.state, 'user', None),
            # Fetch all institutions for the header dropdown
            "all_institutions": session.query(Institution).all()
        },
        "currency_label": "PKR",
    }
    base_context.update(context)
    return templates.TemplateResponse(template_name, base_context)
