"""
Staff API — Thin Routes
────────────────────────
Routes صرف request receive اور StaffLogic کو delegate کریں۔
تمام business logic app/logic/staff.py میں ہے۔
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session
from pydantic import ValidationError

from app.core.database import get_session
from app.models import User, Staff, Student
from app.logic.auth import get_current_user
from app.logic.staff import StaffLogic
from app.logic.attendance import AttendanceLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Staff List ───────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/staff/", methods=["GET", "POST"], name="dms_staff")
async def staff_list(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="staff_view")
    sm = StaffLogic(current_user, session, institution=institution)

    if request.method == "POST":
        data = dict(await request.form())
        if data.get("action") == "update_status":
            sm.save_staff({"id": int(data["staff_id"]), "is_active": data.get("is_active") == "true"})
        return RedirectResponse(url=request.url.path, status_code=303)

    q    = request.query_params.get("q")
    role = request.query_params.get("role")
    ctx  = sm.get_list_context(q=q, role=role)
    ctx["institution"] = institution

    template = "dms/partials/staff_table_partial.html" if request.headers.get("HX-Request") else "dms/staff.html"
    return await TemplateResponse.render(template, request, session, ctx)


# ── 2. Staff Create / Edit ──────────────────────────────────────────────────
@router.api_route("/{institution_slug}/staff/manage/edit/{staff_id}/", methods=["GET", "POST"], name="dms_staff_edit")
@router.api_route("/{institution_slug}/staff/manage/add/",            methods=["GET", "POST"], name="dms_staff_create")
async def staff_create_edit(
    request: Request, institution_slug: str,
    staff_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    sm = StaffLogic(current_user, session, institution=institution)

    if request.method == "POST":
        from app.schemas.forms import StaffFormSchema
        data = dict(await request.form())
        if staff_id:
            data["id"] = staff_id
        try:
            validated = StaffFormSchema(**data)
            sm.save_staff(validated.dict())
            return RedirectResponse(url=request.url_for("dms_staff", institution_slug=institution_slug), status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("dms/staff_form_page.html", request, session, {
                "institution": institution,
                "editing_staff": session.get(Staff, staff_id) if staff_id else None,
                "errors": errors,
                "form_data": data,
            })

    return await TemplateResponse.render("dms/staff_form_page.html", request, session, {
        "institution": institution,
        "editing_staff": session.get(Staff, staff_id) if staff_id else None,
    })


# ── 3. Staff Attendance ─────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/staff/attendance/", methods=["GET", "POST"], name="staff_attendance")
async def staff_attendance(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    am = AttendanceLogic(session, institution=institution, user=current_user)

    target_date_str = request.query_params.get("date")
    try:
        target_date = date.fromisoformat(target_date_str) if target_date_str else date.today()
    except ValueError:
        target_date = date.today()

    if request.method == "POST":
        am.save_bulk(type="staff", post_data=dict(await request.form()), target_date=target_date)
        return RedirectResponse(url=request.url.path + f"?date={target_date}", status_code=303)

    members, active_date, _, __ = am.get_prepared_list(type="staff", target_date=target_date)
    ctx = {"institution": institution, "members": members, "target_date": active_date}
    template = "dms/partials/staff_attendance_rows.html" if request.headers.get("HX-Request") else "dms/staff_attendance.html"
    return await TemplateResponse.render(template, request, session, ctx)


# ── 4. Payroll ──────────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/staff/payroll/", methods=["GET", "POST"], name="staff_payroll")
async def staff_payroll(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="finance")
    sm = StaffLogic(current_user, session, institution=institution)

    month = int(request.query_params.get("month", date.today().month))
    year  = int(request.query_params.get("year",  date.today().year))

    if request.method == "POST":
        data   = dict(await request.form())
        action = data.get("action")
        if action == "process_salary":
            target_staff = session.get(Staff, int(data["staff_id"]))
            if target_staff and target_staff.inst_id == institution.id:
                _sm2 = StaffLogic(current_user, session, target=target_staff)
                _sm2.process_salary(month, year)
        elif action == "bulk_payroll" or action == "bulk_pay":
            sm.execute_bulk_payroll(month, year)
        return RedirectResponse(url=request.url.path + f"?month={month}&year={year}", status_code=303)

    results = sm.get_payroll_stats(month, year)
    total_payable = sum(res['report']['final'] for res in results if res['report'] and res['report']['final'])

    return await TemplateResponse.render("dms/payroll_report.html", request, session, {
        "institution": institution,
        "results": results,
        "total_payable": total_payable,
        "current_month": month,
        "current_year": year,
        "month": month,
        "year": year
    })


# ── 5. Staff Advances ───────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/staff/advances/", methods=["GET", "POST"], name="staff_advances_manage")
async def staff_advances(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="finance")
    sm = StaffLogic(current_user, session, institution=institution)

    if request.method == "POST":
        from app.schemas.forms import StaffAdvanceSchema
        data = dict(await request.form())
        try:
            v = StaffAdvanceSchema(**data)
            sm.record_advance(v.staff_id, v.amount, v.date)
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("dms/staff_manage.html", request, session, {
                "institution": institution,
                "staff_members": sm.get_staff_list(),
                "advances": sm.get_advances(),
                "errors": errors,
                "form_data": data,
            })

    return await TemplateResponse.render("dms/staff_manage.html", request, session, {
        "institution": institution,
        "staff_members": sm.get_staff_list(),
        "advances": sm.get_advances(),
    })


# ── 6. Staff Detail ─────────────────────────────────────────────────────────
@router.get("/{institution_slug}/staff/{staff_id}/", response_class=HTMLResponse, name="dms_staff_detail")
async def staff_detail(
    request: Request, institution_slug: str, staff_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="staff_view")
    staff = session.get(Staff, staff_id)
    if not staff or staff.inst_id != institution.id:
        raise HTTPException(status_code=404)
    return await TemplateResponse.render("dms/staff_detail.html", request, session, {
        "institution": institution, "member": staff
    })


# ── 7. Promote Student → Staff ──────────────────────────────────────────────
@router.post("/{institution_slug}/staff/promote/{student_id}/", name="promote_to_staff")
async def promote_to_staff(
    request: Request, institution_slug: str, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    student = session.get(Student, student_id)
    if not student or student.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="طالب علم نہیں ملا۔")

    sm = StaffLogic(current_user, session, institution=institution)

    def url_for(name, **kwargs):
        return str(request.url_for(name, institution_slug=institution_slug, **kwargs))

    redirect_url, _ = sm.promote_student_to_staff(student, institution, url_for)
    return RedirectResponse(url=redirect_url, status_code=303)
