from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import re
from pydantic import ValidationError

# Internal Imports
from app.db.session import get_session
from app.models import User, Institution, Course, Student
from app.logic.auth import get_current_user
from app.logic.courses import CourseManager
from app.logic.permissions import get_institution_with_access

router = APIRouter()
from app.helper.context import TemplateResponse

# --- 1. course list ---
@router.api_route("/{institution_slug}/course/", methods=["GET", "POST"], response_class=HTMLResponse, name="dms_course")
async def courses_page(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await courses_list_view(request, institution_slug, session, current_user)

@router.get("/{institution_slug}/programs/", response_class=HTMLResponse, name="program_list")
async def programs_list_view(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await courses_list_view(request, institution_slug, session, current_user)

async def courses_list_view(request: Request, institution_slug: str, session: Session, current_user: User):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    cm = CourseManager(session, current_user, institution=institution)
    from app.schemas.forms import CourseFormSchema

    errors = None
    form_data = None

    if request.method == "POST":
        form_data_raw = await request.form()
        data = dict(form_data_raw)
        action = data.get('action')
        
        if action == "delete" and data.get('course_id'):
            cm.delete_course(int(data.get('course_id')))
            return RedirectResponse(url=request.url_for('dms_course', institution_slug=institution_slug), status_code=303)

        try:
            validated_data = CourseFormSchema(**data)
            cm.save_course(validated_data.dict())
            return RedirectResponse(url=request.url_for('dms_course', institution_slug=institution_slug), status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            form_data = data

    courses = session.exec(select(Course).where(Course.inst_id == institution.id).order_by(Course.title)).all()
    
    editing_course = None
    edit_id = request.query_params.get('edit')
    if edit_id:
        editing_course = session.get(Course, int(edit_id))
    
    is_academic_admin = access.can_manage_academics()
    context = {
        "request": request,
        "institution": institution,
        "courses": courses,
        "editing_course": editing_course,
        "is_academic_admin": is_academic_admin,
        "errors": errors,
        "form_data": form_data
    }
    return await TemplateResponse.render("dms/course.html", request, session, context)

# --- 2. course_detail ---
@router.api_route("/{institution_slug}/course/{course_id}/", methods=["GET", "POST"], response_class=HTMLResponse, name="dms_course_detail")
async def course_detail(request: Request, institution_slug: str, course_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    course_obj = session.get(Course, course_id)
    if not course_obj or course_obj.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Course not found")

    cm = CourseManager(session, current_user, target=course_obj)
    errors = None
    
    if request.method == "POST":
        form_data_raw = await request.form()
        data = dict(form_data_raw)
        action = data.get('action')
        
        success, msg, _ = True, "", None
        if action == "enroll":
            success, msg, _ = cm.enroll_student(int(data.get('student_id')), data)
        elif action == "enrollment_update":
            success, msg, _ = cm.update_admission(int(data.get('enrollment_id')), data.get('status'))
        elif action == "enrollment_delete":
            success, msg, _ = cm.delete_admission(int(data.get('enrollment_id')))
        elif action in ["session", "schedule"]:
            data['days'] = form_data_raw.getlist('days')
            success, msg, _ = cm.save_session(data)
        elif action == "session_delete":
            success, msg, _ = cm.delete_session(int(data.get('session_id')))
        elif action == "timetable_delete":
            ids_val = data.get('timetable_ids') or data.get('timetable_id')
            success, msg, _ = cm.delete_timetable_item(str(ids_val))
        elif action == "timetable_save":
            data['days'] = form_data_raw.getlist('days')
            success, msg, _ = cm.save_timetable_item(data)
        elif action == "assign_instructor":
            success, msg, _ = cm.assign_instructor(int(data.get('staff_id')))
        elif action == "remove_instructor":
            success, msg, _ = cm.remove_instructor(int(data.get('staff_id')))
        elif action == "update_course":
            from app.schemas.forms import CourseFormSchema
            try:
                data['id'] = course_id
                validated_data = CourseFormSchema(**data)
                success, msg, _ = cm.save_course(validated_data.dict())
            except Exception as e:
                success, msg = False, str(e)
        elif action == "delete":
            cm.delete_course(course_id)
            return RedirectResponse(url=request.url_for('dms_course', institution_slug=institution_slug), status_code=303)
        elif action == "promote":
            student_ids = request.query_params.getlist('student_ids') or data.get('student_ids', [])
            if isinstance(student_ids, str): student_ids = [student_ids]
            target_course_id = int(data.get('target_course_id'))
            success, msg, _ = cm.promote_students(student_ids, target_course_id)
            
        if not success:
            # If not success, don't redirect, just fall through to render with errors
            errors = {"logic": msg}
        else:
            return RedirectResponse(url=request.url_for('dms_course_detail', institution_slug=institution_slug, course_id=course_id), status_code=303)

    is_academic_admin = access.can_manage_academics()
    context = cm.get_detail_context()
    
    # Extra data for forms
    from app.models import Student, Admission
    from datetime import date as dt_date
    all_students = session.exec(select(Student).where(Student.inst_id == institution.id).order_by(Student.name)).all()
    all_courses = session.exec(select(Course).where(Course.inst_id == institution.id)).all()
    
    context.update({
        "request": request, 
        "institution": institution, 
        "errors": errors,
        "is_academic_admin": is_academic_admin,
        "all_students": all_students,
        "all_courses": all_courses,
        "today": dt_date.today(),
        "enrollment_status_choices": Admission.get_status_choices(),
        "enrollments": context.get('admissions') # Alias if needed
    })
    return await TemplateResponse.render("dms/course_detail.html", request, session, context)

# --- 2.1 Mosque Alias for Program Detail ---
@router.get("/{institution_slug}/programs/{course_id}/", response_class=HTMLResponse, name="program_detail")
async def program_detail(request: Request, institution_slug: str, course_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await course_detail(request, institution_slug, course_id, session, current_user)


# --- 3. Auto Generate Sessions from Timetable (single course) ---
@router.post("/{institution_slug}/course/{course_id}/generate-sessions/", name="course_generate_sessions")
async def generate_course_sessions(
    request: Request,
    institution_slug: str,
    course_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """نظام الاوقات کی بنیاد پر کسی ایک کورس کے سیشن خودکار بنانا۔"""
    import json
    from datetime import date
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    course = session.get(Course, course_id)
    if not course or course.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Course not found.")

    form_data = await request.form() if request.method == "POST" else {}
    data = dict(form_data)

    cm = CourseManager(session, current_user, target=course)

    from_date_str = data.get('from_date')
    to_date_str = data.get('to_date')

    try:
        from_date = date.fromisoformat(from_date_str) if from_date_str else None
        to_date = date.fromisoformat(to_date_str) if to_date_str else None
    except ValueError:
        from_date = to_date = None

    result = cm.generate_sessions_from_timetable(from_date=from_date, to_date=to_date)

    from fastapi.responses import HTMLResponse as HR
    from fastapi.responses import RedirectResponse

    if request.headers.get("HX-Request"):
        color = "emerald" if result["created"] > 0 else "amber"
        html = f"""<div class='p-3 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400 text-sm font-bold'>
            <i class='fas fa-check-circle ml-1'></i> {result['message']}
            <span class='block text-xs opacity-70 mt-1'>{result.get('date_range','')}</span>
        </div>"""
        response = HR(content=html)
        response.headers['HX-Trigger'] = json.dumps({"sessionsGenerated": None, "refreshSessions": None})
        return response

    return RedirectResponse(
        url=request.url_for('dms_course_detail', institution_slug=institution_slug, course_id=course_id),
        status_code=303
    )


# --- 4. Auto Generate Sessions for ALL courses today ---
@router.post("/{institution_slug}/generate-sessions/today/", name="generate_all_sessions_today")
async def generate_all_sessions_today(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """تمام کورسز کے لیے آج کے سیشن ایک کلک میں بنانا۔"""
    import json
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    result = CourseManager.generate_today_sessions_for_institution(session, institution, current_user)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["total_created"] > 0 else "amber"
        details_html = "".join(f"<div class='text-xs opacity-70'>{d}</div>" for d in result.get("details", []))
        html = f"""<div class='p-4 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400'>
            <div class='font-bold text-sm mb-1'><i class='fas fa-magic ml-1'></i> {result['message']}</div>
            {details_html}
        </div>"""
        response = HTMLResponse(content=html)
        response.headers['HX-Trigger'] = json.dumps({"allSessionsGenerated": None})
        return response

    return RedirectResponse(
        url=request.url_for('dashboard', institution_slug=institution_slug),
        status_code=303
    )

