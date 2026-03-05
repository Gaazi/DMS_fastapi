"""
Attendance API — Thin Routes
─────────────────────────────
تمام business logic app/logic/attendance.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session
from datetime import date as dt_date
from typing import Optional

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.attendance import AttendanceLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Attendance Report ─────────────────────────────────────────────────────
@router.get("/{institution_slug}/attendance-report/",
            response_class=HTMLResponse, name="attendance_report")
async def attendance_report(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    am = AttendanceLogic(session, institution=institution, user=current_user)

    start_str = request.query_params.get("start_date")
    end_str   = request.query_params.get("end_date")
    start_date = dt_date.fromisoformat(start_str) if start_str else dt_date.today()
    end_date   = dt_date.fromisoformat(end_str)   if end_str   else dt_date.today()

    return await TemplateResponse.render("dms/attendance_report.html", request, session, {
        "institution": institution,
        "report":      am.get_attendance_report(start_date, end_date),
        "start_date":  start_date,
        "end_date":    end_date,
    })


# ── 2. Bulk Save Attendance ──────────────────────────────────────────────────
@router.post("/{institution_slug}/attendance/bulk-save/", name="save_attendance_bulk")
async def save_attendance_bulk(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    am = AttendanceLogic(session, institution=institution, user=current_user)

    data = dict(await request.form())
    att_type    = data.get("type", "student")
    date_str    = data.get("date")
    target_date = dt_date.fromisoformat(date_str) if date_str else dt_date.today()
    course_raw  = data.get("course_id")
    course_id   = int(course_raw) if course_raw and str(course_raw).strip().isdigit() else None

    am.save_bulk(type=att_type, post_data=data, target_date=target_date, course_id=course_id)
    return RedirectResponse(
        url=request.headers.get("Referer", f"/{institution_slug}/"),
        status_code=303
    )


# ── 3. Session Attendance Redirect ───────────────────────────────────────────
@router.get("/{institution_slug}/session/{session_id}/attendance/",
            name="dms_session_attendance")
async def dms_session_attendance(
    request: Request, institution_slug: str, session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.models.attendance import ClassSession
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    class_session = session.get(ClassSession, session_id)
    if not class_session:
        raise HTTPException(status_code=404, detail="Session not found")

    target_url = request.url_for("student_attendance", institution_slug=institution_slug)
    return RedirectResponse(
        url=f"{target_url}?date={class_session.date}&course_id={class_session.course_id}&session_id={class_session.id}",
        status_code=303,
    )
