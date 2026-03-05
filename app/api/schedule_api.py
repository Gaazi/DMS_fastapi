from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional

# Internal Imports
from app.core.database import get_session
from app.models import User, Institution
from app.logic.auth import get_current_user
from app.logic.schedule import ScheduleManager
from app.logic.permissions import get_institution_with_access

from app.utils.context import TemplateResponse

router = APIRouter()

# --- 1. timetable_view ---
@router.get("/{institution_slug}/timetable/", response_class=HTMLResponse, name="timetable_view")
async def timetable_view(request: Request, institution_slug: str, course_id: Optional[int] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """پورے ادارے یا کسی مخصوص پروگرام کا ٹائم ٹیبل دیکھنا۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    sm = ScheduleManager(current_user, session, institution=institution)
    
    # Get course_id from query params if not provided explicitly in URL (DMS style)
    target_course = course_id or (int(request.query_params.get('course')) if request.query_params.get('course') else None)
    
    context = sm.get_schedule_context(course_id=target_course)
    context.update({"institution": institution})
    
    return await TemplateResponse.render('dms/timetable.html', request, session, context)

