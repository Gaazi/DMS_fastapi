from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, desc
from typing import Optional, List
import json

# Internal Imports
from ..db.session import get_session
from ..models import User, Institution, Exam, Student, Course
from ..logic.auth import get_current_user
from ..logic.exams import ExamManager
from ..logic.permissions import get_institution_with_access
from ..helper.context import TemplateResponse

router = APIRouter()

# --- 1. list_exams ---
@router.get("/{institution_slug}/exams/", response_class=HTMLResponse, name="exam_list")
async def list_exams(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """ادارے کے تمام امتحانات کی فہرست۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    exams = session.exec(select(Exam).where(Exam.inst_id == institution.id).order_by(desc(Exam.date), desc(Exam.id))).all()
    
    return await TemplateResponse.render("dms/exams.html", request, session, {"institution": institution, "exams": exams})

# --- 2. add_exam ---
@router.post("/{institution_slug}/exams/add/", name="exam_add")
async def add_exam(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """نیا امتحان شامل کریں۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    from ..schemas.forms import ExamFormSchema
    from pydantic import ValidationError

    form_data = await request.form()
    data = dict(form_data)
    
    try:
        validated = ExamFormSchema(**data)
        new_exam = Exam(
            inst_id=institution.id,
            title=validated.title,
            date=validated.date,
            is_active=True
        )
        session.add(new_exam)
        session.commit()
        return RedirectResponse(url=f"/{institution_slug}/exams/", status_code=303)
    except ValidationError as e:
        errors = {err['loc'][0]: err['msg'] for err in e.errors()}
        exams = session.exec(select(Exam).where(Exam.inst_id == institution.id).order_by(desc(Exam.date), desc(Exam.id))).all()
        return await TemplateResponse.render("dms/exams.html", request, session, {
            "institution": institution, "exams": exams, "errors": errors, "form_data": data
        })

# --- 3. record_marks_view ---
@router.api_route("/{institution_slug}/exams/{exam_id}/record/", methods=["GET", "POST"], response_class=HTMLResponse, name="record_marks")
async def record_marks_view(request: Request, institution_slug: str, exam_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """نمبر درج کرنےکا طریقہ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    exam_obj = session.get(Exam, exam_id)
    if not exam_obj or exam_obj.inst_id != institution.id:
        raise HTTPException(status_code=404)

    em = ExamManager(session, current_user, exam_obj)
    
    if request.method == "POST":
        form_data = await request.form()
        # یہاں بلک ڈیٹا ہینڈلنگ کی لاجک (DMS سٹائل)
        marks_raw = form_data.get('marks_json')
        if marks_raw:
            marks_data = json.loads(marks_raw)
            em.record_marks(marks_data)
        return RedirectResponse(url=f"/{institution_slug}/exams/", status_code=303)

    # طلبہ کی فہرست حاصل کریں جو اس کورس میں داخل ہیں (اگر امتحان کسی کورس کے لیے ہو)
    students = session.exec(select(Student).where(Student.inst_id == institution.id, Student.is_active == True)).all()
    courses = session.exec(select(Course).where(Course.inst_id == institution.id, Course.is_active == True)).all()

    return await TemplateResponse.render("dms/record_marks.html", request, session, {
        "institution": institution, 
        "exam": exam_obj,
        "students": students,
        "courses": courses
    })

# --- 4. report_card ---
@router.get("/{institution_slug}/exams/{exam_id}/report/{student_id}/", response_class=HTMLResponse, name="report_card")
async def report_card(request: Request, institution_slug: str, exam_id: int, student_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """صرف ایک طالب علم کا رزلٹ کارڈ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='academic_view')
    exam_obj = session.get(Exam, exam_id)
    student = session.get(Student, student_id)
    
    if not exam_obj or not student: raise HTTPException(status_code=404)
    
    em = ExamManager(session, current_user, exam_obj)
    report = em.get_student_report(student_id)
    
    return await TemplateResponse.render("dms/report_card.html", request, session, {
        "institution": institution,
        "student": student,
        "exam": exam_obj,
        "report": report
    })
