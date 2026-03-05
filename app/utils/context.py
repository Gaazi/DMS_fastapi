from typing import Any, Dict, Optional
from sqlmodel import Session, select
from fastapi import Request
from app.models import Institution, User
from app.logic.auth import UserLogic
from app.logic.institution import InstitutionLogic
from fastapi.templating import Jinja2Templates
from app.core.config import settings
import datetime

# Global shared templates instance
templates = Jinja2Templates(directory=["templates", "app/templates"])

from types import SimpleNamespace

class PaginatedData:
    def __init__(self, items, page, total, page_size=20):
        self.object_list = items
        self.number = page
        num_pages = (total + page_size - 1) // page_size if total > 0 else 1
        self.paginator = SimpleNamespace(count=total, num_pages=num_pages)
        self.has_next = page < num_pages
        self.has_previous = page > 1
        self.next_page_number = page + 1
        self.previous_page_number = page - 1
        self.start_index = (page - 1) * page_size + 1 if total > 0 else 0
        self.end_index = min(page * page_size, total)
        self.has_other_pages = num_pages > 1

    def __iter__(self): return iter(self.object_list)
    def __len__(self): return len(self.object_list)
    def __getitem__(self, i): return self.object_list[i]

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

# Custom Filters for Django compatibility
def add_filter(value, arg):
    try: return int(value) + int(arg)
    except: return value

def stringformat_filter(value, arg):
    try:
        if arg == "s": return str(value)
        return ("%" + arg) % value
    except: return value

def truncatechars_filter(value, arg):
    try:
        length = int(arg)
        s = str(value)
        return (s[:length] + "...") if len(s) > length else s
    except: return value

def translate_filter(text):
    translations = {
        "name": "نام",
        "full_name": "نام",
        "father_name": "والد کا نام",
        "mobile": "فون نمبر",
        "course_id": "کورس",
        "agreed_course_fee": "طے شدہ ماہانہ فیس",
        "agreed_admission_fee": "طے شدہ داخلہ فیس",
        "initial_payment": "پہلی ادائیگی",
        "payment_method": "ادائیگی کا طریقہ",
        "address": "پتہ",
        "username": "صارف کا نام",
        "password": "پاس ورڈ",
        "email": "ای میل",
        "gender": "جنس",
        "date_of_birth": "تاریخ پیدائش",
        "amount": "رقم",
        "category": "کیٹیگری",
        "date": "تاریخ",
        "source": "ذریعہ",
        "donor_id": "عطیہ دہندہ",
        "logic": "سسٹم",
        # Days of the Week
        "monday": "پیر", "tuesday": "منگل", "wednesday": "بدھ", "thursday": "جمعرات", "friday": "جمعہ", "saturday": "ہفتہ", "sunday": "اتوار",
        "mon": "پیر", "tue": "منگل", "wed": "بدھ", "thu": "جمعرات", "fri": "جمعہ", "sat": "ہفتہ", "sun": "اتوار"
    }
    return translations.get(str(text).lower(), text)

templates.env.filters["add"] = add_filter
templates.env.filters["add_class"] = add_class
templates.env.filters["date"] = jinja2_date_filter
templates.env.filters["int"] = lambda v: int(v) if v is not None else 0
templates.env.filters["stringformat"] = stringformat_filter
templates.env.filters["truncatechars"] = truncatechars_filter
templates.env.filters["cut"] = lambda v, arg: str(v).replace(arg, "")
def jinja2_time_filter(time_obj, format_str="%H:%M"):
    if not time_obj: return ""
    if hasattr(time_obj, "strftime"):
        return time_obj.strftime(format_str)
    return str(time_obj)

templates.env.filters["time"] = jinja2_time_filter
templates.env.filters["short_id"] = lambda v: str(v).split("-")[-1] if v else ""
templates.env.filters["upper"] = lambda v: str(v).upper() if v else ""
templates.env.filters["dict_key"] = lambda d, k: d.get(k) if isinstance(d, dict) else None
templates.env.filters["translate"] = translate_filter
import json
templates.env.filters["tojson"] = lambda v: json.dumps(v)
templates.env.globals["csrf_token"] = lambda: ""
templates.env.globals["now"] = lambda: datetime.datetime.now()

async def get_global_context(request, session: Session, current_user: Optional[User] = None) -> Dict[str, Any]:
    # Mocking resolver_match for Django template compatibility
    from types import SimpleNamespace
    route = request.scope.get("route")
    route_name = getattr(route, "name", "") if route else ""
    # We use a wrapper since request itself might not allow attribute assignment depending on version, 
    # but FastAPI Request objects are usually mutable in this way or we can just pass it in context.
    try:
        request.resolver_match = SimpleNamespace(url_name=route_name)
    except:
        pass
    institution = None
    # Use path_params or other ways to get slug if standard
    institution_slug = request.path_params.get("institution_slug")
    
    if institution_slug and session:
        institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    
    if not institution and current_user and session:
        institution = session.exec(select(Institution).where(Institution.user_id == current_user.id)).first()

    currency_label = InstitutionLogic.get_currency_label(institution)
    
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
            "notifications_json": [],
            "notifications_url": f"/{institution.slug}/notifications/" if institution else "#",
            "unread_count": 0,
            "user": user_payload,
        },
        "all_institutions": UserLogic.get_user_institutions(current_user, session) if current_user and session else [],
        "user": current_user,
        "errors": {},
        "currency_label": currency_label,
        "current_institution": institution,
        "institution": institution,
        "balance": 0, # Default
        "total_expenses": 0, # Default
        "messages": [],
    }
    
    return context

class TemplateResponse:
    @staticmethod
    async def render(template_name: str, request: Request, session: Session, context: dict = None, status_code: int = 200):
        if context is None: context = {}
        
        # We need this to avoid circular imports if we used app.url_path_for in globals
        # So we can set it here if not already set
        if "url" not in templates.env.globals:
            # We will set this in main.py initialization
            pass

        from app.logic.auth import get_current_user
        current_user = None
        if session:
            try:
                current_user = await get_current_user(request, session)
            except:
                pass
            
        global_ctx = await get_global_context(request, session, current_user)
        global_ctx.update(context)
        
        if "request" not in global_ctx:
            global_ctx["request"] = request
            
        try:
            return templates.TemplateResponse(template_name, global_ctx, status_code=status_code)
        except Exception as e:
            import traceback
            print(f"\nJINJA2 TEMPLATE ERROR in {template_name}:")
            traceback.print_exc()
            raise e
