"""
Schedule API — Thin Routes
───────────────────────────
تمام business logic app/logic/schedule.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session
from typing import Optional

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.schedule import ScheduleLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Timetable View ────────────────────────────────────────────────────────
@router.get("/{institution_slug}/timetable/",
            response_class=HTMLResponse, name="timetable")
async def timetable_view(
    request: Request, institution_slug: str,
    course_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    sm = ScheduleLogic(current_user, session, institution=institution)

    target_course = course_id or (
        int(request.query_params.get("course"))
        if request.query_params.get("course") else None
    )
    ctx = sm.get_schedule_context(course_id=target_course)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/timetable.html", request, session, ctx)
