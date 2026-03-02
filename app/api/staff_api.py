from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
from datetime import date

# Internal Imports
from ..db.session import get_session
from ..models import User, Institution, Staff, Student
from ..logic.auth import get_current_user
from ..logic.staff import StaffManager
from ..logic.attendance import AttendanceManager
from ..logic.permissions import get_institution_with_access
from ..helper.context import TemplateResponse

router = APIRouter()

# --- 1. staff list ---
@router.api_route("/{institution_slug}/staff/", methods=["GET", "POST"], name="dms_staff")
async def staff_list(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='staff_view')
    sm = StaffManager(session, current_user, institution=institution)
    
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        if data.get("action") == "update_status":
            sm.save_staff({"id": int(data.get("staff_id")), "is_active": data.get("is_active") == "true"})
        return RedirectResponse(url=request.url.path, status_code=303)

    q = request.query_params.get('q')
    role = request.query_params.get('role')
    staff_members = sm.get_staff_list(q=q, role=role)
    
    context = {
        "request": request, 
        "institution": institution, 
        "staff_members": staff_members,
        "query": q,
        "role": role
    }
    
    if request.headers.get("HX-Request"): 
        return await TemplateResponse.render("dms/partials/staff_table_partial.html", request, session, context)
    return await TemplateResponse.render("dms/staff.html", request, session, context)

# --- 2. staff_create_edit ---
@router.api_route("/{institution_slug}/staff/manage/edit/{staff_id}/", methods=["GET", "POST"], name="dms_staff_edit")
@router.api_route("/{institution_slug}/staff/manage/add/", methods=["GET", "POST"], name="dms_staff_create")
async def staff_create_edit(request: Request, institution_slug: str, staff_id: Optional[int] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    sm = StaffManager(session, current_user, institution=institution)
    from ..schemas.forms import StaffFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        if staff_id: data["id"] = staff_id
        
        try:
            validated_data = StaffFormSchema(**data)
            sm.save_staff(validated_data.dict())
            return RedirectResponse(url=request.url_for("dms_staff", institution_slug=institution_slug), status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render("dms/staff_form_page.html", request, session, {
                "institution": institution, 
                "editing_staff": session.get(Staff, staff_id) if staff_id else None,
                "errors": errors,
                "form_data": data
            })
        
    editing_staff = session.get(Staff, staff_id) if staff_id else None
    return await TemplateResponse.render("dms/staff_form_page.html", request, session, {"institution": institution, "editing_staff": editing_staff})

# --- 3. staff_attendance ---
@router.api_route("/{institution_slug}/staff/attendance/", methods=["GET", "POST"], name="staff_attendance")
async def staff_attendance(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    am = AttendanceManager(session, institution=institution, user=current_user)
    
    target_date_str = request.query_params.get('date')
    target_date = date.fromisoformat(target_date_str) if target_date_str else date.today()

    if request.method == "POST":
        form_data = await request.form()
        am.save_bulk(type='staff', post_data=dict(form_data), target_date=target_date)
        return RedirectResponse(url=request.url.path + f"?date={target_date}", status_code=303)
        
    members, active_date, _ = am.get_prepared_list(type='staff', target_date=target_date)
    context = {
        "request": request, 
        "institution": institution, 
        "members": members, 
        "target_date": active_date
    }
    
    if request.headers.get("HX-Request"): 
        return await TemplateResponse.render("dms/partials/staff_attendance_rows.html", request, session, context)
    return await TemplateResponse.render("dms/staff_attendance.html", request, session, context)

# --- 4. staff_payroll ---
@router.api_route("/{institution_slug}/staff/payroll/", methods=["GET", "POST"], name="staff_payroll")
async def staff_payroll(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    sm = StaffManager(session, current_user, institution=institution)
    
    month = int(request.query_params.get('month', date.today().month))
    year = int(request.query_params.get('year', date.today().year))

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        action = data.get('action')
        
        if action == "process_salary":
            sm.process_salary(int(data.get("staff_id")), float(data.get("amount")), month, year)
        elif action == "bulk_payroll":
            # Implementation for bulk payroll could go here using sm.process_salary in a loop
            pass
            
        return RedirectResponse(url=request.url.path + f"?month={month}&year={year}", status_code=303)
        
    stats = sm.get_payroll_stats(month, year)
    context = {
        "request": request,
        "institution": institution,
        "stats": stats,
        "current_month": month,
        "current_year": year
    }
    return await TemplateResponse.render("dms/payroll_report.html", request, session, context)

# --- 5. staff_advances ---
@router.api_route("/{institution_slug}/staff/advances/", methods=["GET", "POST"], name="staff_advances_manage")
async def staff_advances_manage(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    sm = StaffManager(current_user, session, institution=institution)
    from ..schemas.forms import StaffAdvanceSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated = StaffAdvanceSchema(**data)
            sm.record_advance(validated.staff_id, validated.amount, validated.adv_date)
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            staff_members = sm.get_staff_list()
            advances = sm.get_advances()
            return await TemplateResponse.render("staff_advances_manage.html", request, session, {
                "institution": institution, "staff_members": staff_members, "advances": advances, "errors": errors, "form_data": data
            })

    staff_members = sm.get_staff_list()
    advances = sm.get_advances()
    return await TemplateResponse.render("staff_advances_manage.html", request, session, {
        "institution": institution, "staff_members": staff_members, "advances": advances
    })

# --- 6. promote_to_staff ---
@router.post("/{institution_slug}/staff/promote/{student_id}/", name="promote_to_staff")
async def promote_to_staff(request: Request, institution_slug: str, student_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    
    student = session.get(Student, student_id)
    if not student or student.inst_id != institution.id:
        raise HTTPException(status_code=404)
        
    from ..logic.roles import Role
    from datetime import date
    
    # Check if existing staff (by mobile or name)
    existing_staff = None
    if student.mobile:
        existing_staff = session.exec(select(Staff).where(Staff.inst_id == institution.id, Staff.mobile == student.mobile)).first()
    if not existing_staff:
        existing_staff = session.exec(select(Staff).where(Staff.inst_id == institution.id, Staff.name == student.name)).first()
        
    if existing_staff:
        # User is warned in frontend, redirecting with a query param
        return RedirectResponse(
            url=request.url_for("dms_staff_edit", institution_slug=institution_slug, staff_id=existing_staff.id) + "?msg=already_exists", 
            status_code=303
        )
        
    # Copy profile to staff
    new_staff = Staff(
        inst_id=institution.id,
        name=student.name,
        mobile=student.mobile,
        email=student.email,
        address=student.address,
        role=Role.VOLUNTEER.value,
        base_salary=0,
        hire_date=date.today(),
        is_active=True
    )
    session.add(new_staff)
    session.commit()
    session.refresh(new_staff)
    
    return RedirectResponse(url=request.url_for("dms_staff_edit", institution_slug=institution_slug, staff_id=new_staff.id), status_code=303)

