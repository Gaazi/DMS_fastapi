from fastapi import APIRouter, Request, Depends, Form
from sqlalchemy.orm import Session
from database import get_session
from models import Institution, Student, Course, Admission, Fee
from templating import render_template
from typing import Optional

router = APIRouter(prefix="/dms/{slug}/students", tags=["students"])

@router.get("/", name="students")
async def student_dashboard(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    courses = session.query(Course).filter(Course.inst_id == institution.id, Course.is_active == True).all()
    
    context = {
        "institution": institution,
        "courses": courses,
        "selected_course": request.query_params.get("course"),
        "query": request.query_params.get("q"),
        "stats": {
            "total": session.query(Student).filter(Student.inst_id == institution.id).count(),
            "active": session.query(Student).filter(Student.inst_id == institution.id, Student.is_active == True).count(),
            "inactive": session.query(Student).filter(Student.inst_id == institution.id, Student.is_active == False).count(),
            "today": 0
        }
    }
    return render_template("dms/students.html", request, context, session)

@router.get("/list", name="student_list")
async def student_list(
    request: Request, 
    slug: str, 
    q: Optional[str] = None, 
    status: str = "active", 
    course: Optional[int] = None, 
    session: Session = Depends(get_session)
):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    query = session.query(Student).filter(Student.inst_id == institution.id)
    if q:
        query = query.filter(Student.name.contains(q) | Student.reg_id.contains(q))
    if status == "active":
        query = query.filter(Student.is_active == True)
    elif status == "inactive":
        query = query.filter(Student.is_active == False)
        
    if course:
        query = query.join(Admission).filter(Admission.course_id == course)
        
    students = query.order_by(Student.name).all()
    
    context = {
        "institution": institution,
        "students": students,
        "is_academic_admin": True
    }
    return render_template("dms/partials/student_list.html", request, context, session)

@router.get("/detail/{student_id}", name="student_detail")
async def student_detail(request: Request, slug: str, student_id: int, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    student = session.query(Student).filter(Student.id == student_id, Student.inst_id == institution.id).first()
    if not student: return {"error": "Student not found"}
    
    context = {
        "institution": institution,
        "student": student,
        "fees": session.query(Fee).filter(Fee.student_id == student_id).all(),
        "enrollments": student.admissions,
        "wallet_balance": student.wallet_balance,
        "is_academic_admin": True,
        "can_view_academics": True,
        "is_finance_admin": True,
    }
    return render_template("dms/student_detail.html", request, context, session)
