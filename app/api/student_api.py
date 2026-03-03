from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import re
from datetime import datetime, date

# Internal Imports
from app.db.session import get_session
from app.models import User, Institution, Student
from app.logic.auth import get_current_user
from app.logic.students import StudentManager
from app.logic.attendance import AttendanceManager
from app.logic.permissions import get_institution_with_access
from app.helper.context import TemplateResponse, PaginatedData

router = APIRouter()

# --- 1. students list ---
@router.api_route("/{institution_slug}/students/", methods=["GET", "POST"], response_class=HTMLResponse, name="students")
async def students_page(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await students_list_view(request, institution_slug, session, current_user)

@router.get("/{institution_slug}/musalleen/", response_class=HTMLResponse, name="musalleen_list")
async def musalleen_page(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await students_list_view(request, institution_slug, session, current_user)

async def students_list_view(request: Request, institution_slug: str, session: Session, current_user: User):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    sm = StudentManager(session, current_user, institution=institution)
    
    q = request.query_params.get('q')
    course_id = request.query_params.get('course_id')
    status = request.query_params.get('status', 'active')
    page = int(request.query_params.get('page', 1))

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        action = data.get('action')
        
        if action == "save_student":
            # Extract enrollment data if present
            enroll_data = {
                "course_id": data.get("course_id"),
                "agreed_fee": data.get("agreed_fee"),
                "admission_fee": data.get("admission_fee"),
                "initial_payment": data.get("initial_payment", 0),
                "payment_method": data.get("payment_method", "Cash")
            }
            sm.save_student(data, enroll_data if enroll_data["course_id"] else None)
        elif action == "update_status":
            sm.update_status(int(data.get("student_id")), data.get("is_active") == "true")
            
        return RedirectResponse(url=request.url.path, status_code=303)

    data = sm.get_student_list(q=q, course_id=course_id, status=status, page=page)
    context = {
        "request": request,
        "institution": institution,
        "students": PaginatedData(data["students"], page, data["total"]),
        "total_count": data["total"],
        "stats": data["stats"],
        "query": q,
        "current_status": status,
        "page": page
    }
    
    if request.headers.get("HX-Request"):
        return await TemplateResponse.render("dms/partials/student_list.html", request, session, context)
            
    return await TemplateResponse.render("dms/students.html", request, session, context)

# --- 2. student_detail ---
@router.api_route("/{institution_slug}/students/detail/{student_id}/", methods=["GET", "POST"], response_class=HTMLResponse, name="student_detail")
async def student_detail(request: Request, institution_slug: str, student_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    sm = StudentManager(session, current_user, institution=institution)
    
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        action = data.get('action')
        
        if action == "update_student":
            sm.save_student(data)
        elif action == "promote":
            sm.promote_student(student_id, int(data.get("new_course_id")))
            
        return RedirectResponse(url=request.url.path, status_code=303)

    context = sm.get_student_detail_context(student_id)
    context.update({"request": request, "institution": institution})
    return await TemplateResponse.render("dms/student_detail.html", request, session, context)

# --- 2.1 student_dashboard ---
@router.api_route("/{institution_slug}/students/dashboard/{student_id}/", methods=["GET"], response_class=HTMLResponse, name="student_dashboard")
async def student_dashboard(request: Request, institution_slug: str, student_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    sm = StudentManager(session, current_user, institution=institution)
    
    # get_student_detail_context performs internal checks
    context = sm.get_student_detail_context(student_id)
    context.update({"request": request, "institution": institution})
    return await TemplateResponse.render("dms/student_dashboard.html", request, session, context)

# --- 3. admission ---
@router.api_route("/{institution_slug}/students/admission/", methods=["GET", "POST"], response_class=HTMLResponse, name="admission")
async def admission(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    
    from app.schemas.forms import StudentAdmissionSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        
        try:
            validated_data = StudentAdmissionSchema(**data)
            
            sm = StudentManager(session, current_user, institution=institution)
            
            # Prepare data for StudentManager
            student_data = validated_data.dict()
            student_data['full_name'] = student_data.pop('name') # Logic expects full_name
            
            enroll_data = {
                "course_id": validated_data.course_id,
                "agreed_fee": validated_data.agreed_course_fee,
                "admission_fee": validated_data.agreed_admission_fee,
                "initial_payment": validated_data.initial_payment,
                "payment_method": validated_data.payment_method
            }
            
            sm.save_student(student_data, enroll_data if validated_data.course_id else None)
            return RedirectResponse(url=request.url_for("students", institution_slug=institution_slug), status_code=303)
            
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            courses = session.exec(select(Course).where(Course.inst_id == institution.id)).all()
            selected_course = session.get(Course, int(data.get('course_id'))) if data.get('course_id') else None
            
            context = {
                "request": request, 
                "institution": institution, 
                "courses": courses,
                "errors": errors,
                "form_data": data,
                "selected_course": selected_course
            }
            return await TemplateResponse.render("dms/admission.html", request, session, context)

    course_id = request.query_params.get("course_id")
    selected_course = session.get(Course, int(course_id)) if course_id else None
    
    courses = session.exec(select(Course).where(Course.inst_id == institution.id)).all()
    context = {
        "request": request, 
        "institution": institution, 
        "courses": courses,
        "selected_course": selected_course
    }
    return await TemplateResponse.render("dms/admission.html", request, session, context)

# --- 4. student_attendance ---
@router.api_route("/{institution_slug}/students/attendance/", methods=["GET", "POST"], response_class=HTMLResponse, name="student_attendance")
async def student_attendance(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    am = AttendanceManager(session, institution=institution, user=current_user)
    
    target_date_str = request.query_params.get('date')
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else date.today()
    course_id = request.query_params.get('course_id')
    if course_id: course_id = int(course_id)

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        # Parse date from form if redirected
        am.save_bulk(type='student', post_data=data, target_date=target_date, course_id=course_id)
        return RedirectResponse(url=request.url.path + f"?date={target_date}&course_id={course_id or ''}", status_code=303)

    members, active_date, active_course_id = am.get_prepared_list(type='student', target_date=target_date, course_id=course_id)
    
    from app.models import Course
    courses = session.exec(select(Course).where(Course.inst_id == institution.id)).all()
    
    context = {
        "request": request,
        "institution": institution,
        "members": members,
        "target_date": active_date,
        "course_id": active_course_id,
        "courses": courses
    }
    
    if request.headers.get("HX-Request"):
        return await TemplateResponse.render("dms/partials/student_attendance_table.html", request, session, context)
    return await TemplateResponse.render("dms/student_attendance.html", request, session, context)

