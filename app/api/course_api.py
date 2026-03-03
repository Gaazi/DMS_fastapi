from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import re

# Internal Imports
from app.db.session import get_session
from app.models import User, Institution, Course
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
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = CourseFormSchema(**data)
            cm.save_course(validated_data.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            courses = session.exec(select(Course).where(Course.inst_id == institution.id).order_by(Course.title)).all()
            return await TemplateResponse.render("dms/course.html", request, session, {
                "request": request, "institution": institution, "courses": courses, "errors": errors, "form_data": data
            })

    courses = session.exec(select(Course).where(Course.inst_id == institution.id).order_by(Course.title)).all()
    context = {
        "request": request,
        "institution": institution,
        "courses": courses
    }
    return await TemplateResponse.render("dms/course.html", request, session, context)

# --- 2. course_detail ---
@router.api_route("/{institution_slug}/course/{course_id}/", methods=["GET", "POST"], response_class=HTMLResponse, name="course_detail")
async def course_detail(request: Request, institution_slug: str, course_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    course_obj = session.get(Course, course_id)
    if not course_obj or course_obj.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Course not found")

    cm = CourseManager(session, current_user, target=course_obj)
    
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        action = data.get('action')
        
        if action == "enroll":
            cm.enroll_student(int(data.get('student_id')), data)
        elif action == "schedule":
            cm.save_session(data)
        elif action == "update_course":
            data['id'] = course_id
            cm.save_course(data)
            
        return RedirectResponse(url=request.url.path, status_code=303)

    context = cm.get_detail_context()
    context.update({"request": request, "institution": institution})
    return await TemplateResponse.render("dms/course_detail.html", request, session, context)

# --- 2.1 Mosque Alias for Program Detail ---
@router.get("/{institution_slug}/programs/{course_id}/", response_class=HTMLResponse, name="programs_detail")
async def program_detail(request: Request, institution_slug: str, course_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await course_detail(request, institution_slug, course_id, session, current_user)
