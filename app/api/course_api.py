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
    
    if request.method == "POST":
        form_data_raw = await request.form()
        data = dict(form_data_raw)
        action = data.get('action')
        
        if action == "enroll":
            cm.enroll_student(int(data.get('student_id')), data)
        elif action == "enrollment_update":
            cm.update_admission(int(data.get('enrollment_id')), data.get('status'))
        elif action == "enrollment_delete":
            cm.delete_admission(int(data.get('enrollment_id')))
        elif action in ["session", "schedule"]:
            cm.save_session(data)
        elif action == "session_delete":
            cm.delete_session(int(data.get('session_id')))
        elif action == "update_course":
            from app.schemas.forms import CourseFormSchema
            try:
                data['id'] = course_id
                validated_data = CourseFormSchema(**data)
                cm.save_course(validated_data.dict())
            except Exception as e:
                # You might want to pass errors back to context here
                print(f"Error updating course: {e}")
        elif action == "delete":
            cm.delete_course(course_id)
            return RedirectResponse(url=request.url_for('dms_course', institution_slug=institution_slug), status_code=303)
            
        return RedirectResponse(url=request.url_for('dms_course_detail', institution_slug=institution_slug, course_id=course_id), status_code=303)

    is_academic_admin = access.can_manage_academics()
    context = cm.get_detail_context()
    
    # Extra data for forms
    from app.models import Student, Admission
    from datetime import date as dt_date
    all_students = session.exec(select(Student).where(Student.inst_id == institution.id).order_by(Student.name)).all()
    
    context.update({
        "request": request, 
        "institution": institution, 
        "is_academic_admin": is_academic_admin,
        "all_students": all_students,
        "today": dt_date.today(),
        "enrollment_status_choices": Admission.get_status_choices(),
        "enrollments": context.get('admissions') # Alias if needed
    })
    return await TemplateResponse.render("dms/course_detail.html", request, session, context)

# --- 2.1 Mosque Alias for Program Detail ---
@router.get("/{institution_slug}/programs/{course_id}/", response_class=HTMLResponse, name="program_detail")
async def program_detail(request: Request, institution_slug: str, course_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await course_detail(request, institution_slug, course_id, session, current_user)
