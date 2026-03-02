from fastapi import APIRouter, Request, Depends, Form
from sqlalchemy.orm import Session
from database import get_session
from models import Institution, Staff
from templating import render_template
from typing import Optional
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/dms/{slug}/staff", tags=["staff"])

@router.get("/", name="dms_staff")
async def list_staff(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    staff_members = session.query(Staff).filter(Staff.inst_id == institution.id).all()
    
    context = {
        "institution": institution,
        "staff_members": staff_members,
        "total_count": len(staff_members),
        "active_count": sum(1 for s in staff_members if s.is_active),
    }
    return render_template("dms/staff.html", request, context, session)

@router.get("/manage/add", name="dms_staff_create")
@router.get("/manage/edit/{staff_id}", name="dms_staff_edit")
async def staff_form(request: Request, slug: str, staff_id: Optional[int] = None, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    editing_staff = None
    if staff_id:
        editing_staff = session.get(Staff, staff_id)
        
    context = {
        "institution": institution,
        "editing_staff": editing_staff,
        "form": {},
    }
    return render_template("dms/staff_form_page.html", request, context, session)

@router.post("/manage/add")
@router.post("/manage/edit/{staff_id}")
async def process_staff(
    request: Request,
    slug: str,
    name: str = Form(...),
    role: str = Form("teacher"),
    mobile: Optional[str] = Form(None),
    staff_id: Optional[int] = Form(None),
    session: Session = Depends(get_session)
):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if staff_id:
        staff = session.get(Staff, staff_id)
        staff.name = name
        staff.role = role
        staff.mobile = mobile
    else:
        staff = Staff(
            inst_id=institution.id,
            name=name,
            role=role,
            mobile=mobile,
            is_active=True
        )
        session.add(staff)
        
    session.commit()
    return RedirectResponse(url=f"/dms/{slug}/staff", status_code=303)
