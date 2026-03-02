from fastapi import APIRouter, Request, Depends, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_session
from models import Institution, Student, Staff, Course, Income, Expense, Admission
from templating import render_template, django_now
from typing import Optional
from datetime import date as dt_date
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/dms/{slug}", tags=["institutions"])

@router.get("/", name="dashboard")
async def dashboard(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    stats = {
        "students": session.query(Student).filter(Student.inst_id == institution.id, Student.is_active == True).count(),
        "staff": session.query(Staff).filter(Staff.inst_id == institution.id, Staff.is_active == True).count(),
        "courses": session.query(Course).filter(Course.inst_id == institution.id, Course.is_active == True).count(),
    }
    
    context = {
        "institution": institution,
        "is_admin": True,
        "stats": stats,
        "finance": {
            "revenue": {"total": session.query(func.sum(Income.amount)).filter(Income.inst_id == institution.id).scalar() or 0},
            "total_expenses": session.query(func.sum(Expense.amount)).filter(Expense.inst_id == institution.id).scalar() or 0,
            "balance": 0 
        },
        "attendance": {"present_count": 0},
        "recent_sessions": [],
        "upcoming_sessions": [],
        "alerts": {"defaulters": [], "full_classes": [], "count": 0},
        "today": django_now("Y-m-d"),
    }
    context["finance"]["balance"] = context["finance"]["revenue"]["total"] - context["finance"]["total_expenses"]
    return render_template("dms/dashboard.html", request, context, session)

@router.get("/admission", name="admission")
async def admission_form(request: Request, slug: str, edit: Optional[int] = None, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    editing_student = None
    if edit:
        editing_student = session.get(Student, edit)
        
    courses = session.query(Course).filter(Course.inst_id == institution.id, Course.is_active == True).all()
    
    context = {
        "institution": institution,
        "editing_student": editing_student,
        "courses": courses,
        "form": {}, 
    }
    return render_template("dms/admission.html", request, context, session)

@router.post("/admission")
async def process_admission(
    request: Request, 
    slug: str, 
    name: str = Form(...),
    father_name: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    course_id: Optional[int] = Form(None, alias="course"),
    student_id: Optional[int] = Form(None),
    session: Session = Depends(get_session)
):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    if student_id:
        student = session.get(Student, student_id)
        student.name = name
        student.father_name = father_name
        student.mobile = mobile
    else:
        student = Student(
            inst_id=institution.id,
            name=name,
            father_name=father_name,
            mobile=mobile,
            is_active=True
        )
        session.add(student)
        session.flush()
        
    if course_id:
        existing = session.query(Admission).filter(Admission.student_id == student.id, Admission.course_id == course_id, Admission.status == "active").first()
        if not existing:
            admission = Admission(
                student_id=student.id,
                course_id=course_id,
                status="active",
                admission_date=dt_date.today()
            )
            session.add(admission)
            
    session.commit()
    return RedirectResponse(url=f"/dms/{slug}/students", status_code=303)
