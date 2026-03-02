from typing import Any, Dict, Optional
from sqlmodel import Session, select
from fastapi import Request
from ..models import Institution, User
from ..logic.auth import UserManager
from ..logic.institution import InstitutionManager
from fastapi.templating import Jinja2Templates
from app.core.config import settings
import datetime

# Global shared templates instance
templates = Jinja2Templates(directory=["templates", "app/templates"])

def add_class(value, class_name):
    """Simple filter to simulate widget_tweaks add_class"""
    return value # Fallback

def jinja2_date_filter(date_obj, format_str="%d %b %Y"):
    if not date_obj:
        return ""
    if isinstance(date_obj, str):
        try:
            from datetime import datetime
            date_obj = datetime.fromisoformat(date_obj)
        except:
            return date_obj
    return date_obj.strftime(format_str)

templates.env.filters["add_class"] = add_class
templates.env.filters["date"] = jinja2_date_filter
templates.env.globals["csrf_token"] = lambda: ""

async def get_global_context(request, session: Session, current_user: Optional[User] = None) -> Dict[str, Any]:
    # ... (existing content logic)
    institution = None
    # Use path_params or other ways to get slug if standard
    institution_slug = request.path_params.get("institution_slug")
    
    if institution_slug:
        institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    
    if not institution and current_user:
        institution = session.exec(select(Institution).where(Institution.user_id == current_user.id)).first()

    currency_label = InstitutionManager.get_currency_label(institution)
    
    user_payload = {"name": "مہمان", "email": "", "role": "", "initials": ""}
    if current_user:
        name = current_user.username
        initials = name[:2].upper()
        role = "Admin" if current_user.is_superuser else "User"
        user_payload = {
            "name": name,
            "email": current_user.email or "",
            "role": role,
            "initials": initials
        }

    # Global Context
    context = {
        "request": request,
        "PROJECT_NAME": settings.PROJECT_NAME,
        "VERSION": settings.VERSION,
        "date_today": datetime.date.today().isoformat(),
        "csrf_token": lambda: "", # Dummy for now
        "dms_header": {
            "notifications_json": "[]",
            "unread_count": 0,
            "user": user_payload,
            "all_institutions": UserManager.get_user_institutions(current_user, session) if current_user else []
        },
        "currency_label": currency_label,
        "current_institution": institution,
        "messages": [],
    }
    
    return context

class TemplateResponse:
    @staticmethod
    async def render(template_name: str, request: Request, session: Session, context: dict = None):
        if context is None: context = {}
        
        # We need this to avoid circular imports if we used app.url_path_for in globals
        # So we can set it here if not already set
        if "url" not in templates.env.globals:
            # We will set this in main.py initialization
            pass

        from ..logic.auth import get_current_user
        current_user = None
        try:
            current_user = await get_current_user(request, session)
        except:
            pass
            
        global_ctx = await get_global_context(request, session, current_user)
        global_ctx.update(context)
        
        if "request" not in global_ctx:
            global_ctx["request"] = request
            
        return templates.TemplateResponse(template_name, global_ctx)
