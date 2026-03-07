"""
Student API — Thin Routes
──────────────────────────
Routes صرف request receive اور StudentLogic کو delegate کریں۔
تمام business logic app/logic/students.py میں ہے۔
"""
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session
from pydantic import ValidationError

from app.core.database import get_session
from app.models import User, Student, Course
from app.logic.auth import get_current_user
from app.logic.students import StudentLogic
from app.logic.courses import CourseLogic
from app.logic.attendance import AttendanceLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse, PaginatedData

router = APIRouter()


# ── 1. Students List ────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/students/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="students")
async def students_page(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    sm = StudentLogic(session, current_user, institution=institution)

    if request.method == "POST":
        data = dict(await request.form())
        sm.handle_post_list(data.get("action"), data)
        return RedirectResponse(url=request.url.path, status_code=303)

    q       = request.query_params.get("q")
    status  = request.query_params.get("status", "active")
    page    = int(request.query_params.get("page", 1))
    course_id = request.query_params.get("course_id")

    data = sm.get_student_list(q=q, course_id=course_id, status=status, page=page)
    ctx = {
        "institution": institution,
        "students": PaginatedData(data["students"], page, data["total"]),
        "total_count": data["total"],
        "stats": data["stats"],
        "query": q,
        "current_status": status,
        "page": page,
    }
    template = "dms/partials/student_list.html" if request.headers.get("HX-Request") else "dms/students.html"
    return await TemplateResponse.render(template, request, session, ctx)


# Mosque aliases
@router.get("/{institution_slug}/musalleen/", response_class=HTMLResponse, name="musalleen_list")
async def musalleen_page(request: Request, institution_slug: str,
                         session: Session = Depends(get_session),
                         current_user: User = Depends(get_current_user)):
    return await students_page(request, institution_slug, session, current_user)

@router.api_route("/{institution_slug}/musalleen/admission/", methods=["GET", "POST"], response_class=HTMLResponse, name="musallee_admission")
async def musallee_admission(request: Request, institution_slug: str,
                             session: Session = Depends(get_session),
                             current_user: User = Depends(get_current_user)):
    return await admission(request, institution_slug, session, current_user)

@router.api_route("/{institution_slug}/musalleen/detail/{student_id}/", methods=["GET", "POST"], response_class=HTMLResponse, name="musalleen_detail")
async def musalleen_detail(request: Request, institution_slug: str, student_id: int,
                           session: Session = Depends(get_session),
                           current_user: User = Depends(get_current_user)):
    return await student_detail(request, institution_slug, student_id, session, current_user)



# ── 2. Student Detail ───────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/students/detail/{student_id}/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="student_detail")
async def student_detail(
    request: Request, institution_slug: str, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    sm = StudentLogic(session, current_user, institution=institution)

    if request.method == "POST":
        data = dict(await request.form())
        result = sm.handle_post_detail(data.get("action"), data, student_id)
        if result == "redirect_to_list":
            return RedirectResponse(url=request.url_for("students", institution_slug=institution_slug), status_code=303)
        return RedirectResponse(url=request.url.path, status_code=303)

    ctx = sm.get_student_detail_context(student_id)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/student_detail.html", request, session, ctx)


# ── 2.1 Student Dashboard ───────────────────────────────────────────────────
@router.get("/{institution_slug}/students/dashboard/{student_id}/",
            response_class=HTMLResponse, name="student_dashboard")
async def student_dashboard(
    request: Request, institution_slug: str, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    sm = StudentLogic(session, current_user, institution=institution)
    ctx = sm.get_student_detail_context(student_id)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/student_dashboard.html", request, session, ctx)


# ── 3. Admission ────────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/students/admission/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="admission")
async def admission(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    sm = StudentLogic(session, current_user, institution=institution)

    if request.method == "POST":
        data = dict(await request.form())
        student_id_raw = data.get("student_id")
        
        # Edit existing student
        if student_id_raw:
            sm.save_student(data)
            return RedirectResponse(url=request.url_for("student_detail", institution_slug=institution_slug, student_id=int(student_id_raw)), status_code=303)
        
        # New admission
        from app.schemas.forms import StudentAdmissionSchema
        try:
            validated = StudentAdmissionSchema(**data)
            vd = validated.dict()
            enroll_data = {
                "course_id": validated.course_id,
                "agreed_fee": validated.agreed_course_fee,
                "admission_fee": validated.agreed_admission_fee,
                "initial_payment": validated.initial_payment,
                "payment_method": validated.payment_method,
                "roll_no": validated.roll_no,
            }
            sm.save_student(vd, enroll_data if validated.course_id else None)
            return RedirectResponse(url=request.url_for("students", institution_slug=institution_slug), status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            ctx = sm.get_admission_context(data.get("course_id"))
            ctx.update({"institution": institution, "errors": errors, "form_data": data})
            return await TemplateResponse.render("dms/admission.html", request, session, ctx)

    # GET — check if editing
    student_id_raw = request.query_params.get("student_id")
    course_id = request.query_params.get("course_id")
    ctx = sm.get_admission_context(course_id)
    ctx["institution"] = institution
    
    if student_id_raw:
        editing_student = session.get(Student, int(student_id_raw))
        ctx["editing_student"] = editing_student
    
    return await TemplateResponse.render("dms/admission.html", request, session, ctx)


# ── 4. Student Attendance ───────────────────────────────────────────────────
@router.api_route("/{institution_slug}/students/attendance/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="student_attendance")
async def student_attendance(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    am = AttendanceLogic(session, institution=institution, user=current_user)

    target_date_str = request.query_params.get("date")
    course_id_raw   = request.query_params.get("course_id")
    session_id_raw  = request.query_params.get("session_id")

    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date() if target_date_str else date.today()
    except (ValueError, TypeError):
        target_date = date.today()

    course_id  = int(course_id_raw)  if course_id_raw  and course_id_raw.isdigit()  else None
    session_id = int(session_id_raw) if session_id_raw and session_id_raw.isdigit() else None

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        data["days"] = form_data.getlist("days")

        try:
            effective_date = datetime.strptime(data.get("date", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            effective_date = target_date

        post_cid = data.get("course_id")
        effective_course_id = int(post_cid) if post_cid and post_cid.isdigit() else course_id

        if data.get("action") == "add_session" and effective_course_id:
            cm = CourseLogic(session, current_user, target=session.get(Course, effective_course_id))
            ok, _, new_sess = cm.save_session(data)
            if ok:
                return RedirectResponse(
                    url=request.url.path + f"?date={effective_date}&course_id={effective_course_id}&session_id={new_sess.id}",
                    status_code=303
                )

        am.save_bulk(type="student", post_data=data, target_date=effective_date, course_id=effective_course_id)
        query = f"?date={effective_date}"
        if effective_course_id: query += f"&course_id={effective_course_id}"
        if data.get("session_id"):  query += f"&session_id={data['session_id']}"
        return RedirectResponse(url=request.url.path + query, status_code=303)

    members, active_date, active_course_id, active_session_id = am.get_prepared_list(
        type="student", target_date=target_date, course_id=course_id, session_id=session_id
    )
    from sqlmodel import select
    courses = session.exec(select(Course).where(Course.inst_id == institution.id).order_by(Course.title)).all()
    ctx = {
        "institution": institution,
        "members": members,
        "selected_date": active_date,
        "selected_course_id": str(active_course_id) if active_course_id else "",
        "selected_course": next((c for c in courses if c.id == active_course_id), None),
        "selected_session_id": str(active_session_id) if active_session_id else "",
        "sessions": am.get_sessions(active_course_id, active_date),
        "all_courses": courses,
    }
    template = ("dms/partials/student_attendance_content.html"
                if request.headers.get("HX-Request") and not request.query_params.get("full_page")
                else "dms/student_attendance.html")
    return await TemplateResponse.render(template, request, session, ctx)


# ── 5. ID Card ──────────────────────────────────────────────────────────────
@router.get("/{institution_slug}/students/{student_id}/id-card/",
            response_class=HTMLResponse, name="student_id_card")
async def student_id_card(
    request: Request, institution_slug: str, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    student = session.get(Student, student_id)
    if not student or student.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Student not found")

    from sqlmodel import select
    from app.models import Admission
    ctx = {
        "institution": institution,
        "student": student,
        "admissions": session.exec(select(Admission).where(Admission.student_id == student.id)).all(),
    }
    return await TemplateResponse.render("dms/id_card.html", request, session, ctx)


# ── 6. Student Self-Portal ──────────────────────────────────────────────────
@router.get("/{institution_slug}/students/{student_id}/dashboard/",
            response_class=HTMLResponse, name="student_dashboard_scoped")
async def student_self_dashboard(
    request: Request, institution_slug: str, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    sm = StudentLogic(session, current_user, institution=institution)
    ctx = sm.get_self_dashboard_context(student_id=student_id, requesting_user_id=current_user.id)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/student_dashboard.html", request, session, ctx)
