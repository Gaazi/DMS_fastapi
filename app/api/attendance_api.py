from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from typing import Optional

# Internal Imports
from app.core.database import get_session
from app.models import User, Institution
from app.logic.auth import get_current_user
from app.logic.attendance import AttendanceManager
from app.logic.permissions import get_institution_with_access

router = APIRouter()
from app.utils.context import TemplateResponse
from datetime import date as dt_date
from app.models.attendance import ClassSession

@router.get("/{institution_slug}/attendance-report/", response_class=HTMLResponse, name="attendance_report")
async def attendance_report(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """ادارے کی مجموعی حاضری کی رپورٹ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    am = AttendanceManager(session, institution=institution, user=current_user)
    
    start_date_str = request.query_params.get('start_date')
    end_date_str = request.query_params.get('end_date')
    
    start_date = dt_date.fromisoformat(start_date_str) if start_date_str else dt_date.today()
    end_date = dt_date.fromisoformat(end_date_str) if end_date_str else dt_date.today()
    
    report_data = am.get_attendance_report(start_date, end_date)
    context = {
        "request": request,
        "institution": institution,
        "report": report_data,
        "start_date": start_date,
        "end_date": end_date
    }
    return await TemplateResponse.render("dms/attendance_report.html", request, session, context)

@router.post("/{institution_slug}/attendance/bulk-save/", name="save_attendance_bulk")
async def save_attendance_bulk(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """بلک میں حاضری محفوظ کرنا۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    am = AttendanceManager(session, institution=institution, user=current_user)
    
    form_data = await request.form()
    data = dict(form_data)
    
    type = data.get('type', 'student')
    target_date_str = data.get('date')
    target_date = dt_date.fromisoformat(target_date_str) if target_date_str else dt_date.today()
    course_id_raw = data.get('course_id')
    course_id = int(course_id_raw) if course_id_raw and str(course_id_raw).strip().isdigit() else None
    
    am.save_bulk(type=type, post_data=data, target_date=target_date, course_id=course_id)
    
    return RedirectResponse(url=request.headers.get("Referer", f"/{institution_slug}/dashboard"), status_code=303)


@router.get("/{institution_slug}/session/{session_id}/attendance/", name="dms_session_attendance")
async def dms_session_attendance(request: Request, institution_slug: str, session_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """مخصوص سیشن کے لیے حاضری کے پیج پر ری ڈائریکٹ کرنا۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    class_session = session.get(ClassSession, session_id)
    if not class_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Redirect to global student attendance with session's date and course
    target_url = request.url_for('student_attendance', institution_slug=institution_slug)
    return RedirectResponse(url=f"{target_url}?date={class_session.date}&course_id={class_session.course_id}&session_id={class_session.id}", status_code=303)
