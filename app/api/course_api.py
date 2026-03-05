"""
Course API — Thin Routes
─────────────────────────
Routes صرف request receive کریں اور CourseLogic کو delegate کریں۔
تمام business logic app/logic/courses.py میں ہے۔
"""
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.core.database import get_session
from app.models import User, Course
from app.logic.auth import get_current_user
from app.logic.courses import CourseLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Course List ─────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/course/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="dms_course")
async def courses_page(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    cm = CourseLogic(session, current_user, institution=institution)

    errors, form_data = None, None

    if request.method == "POST":
        data = dict(await request.form())
        action = data.get("action")

        if action == "delete":
            cm.handle_post_list(action, data)
            return RedirectResponse(url=request.url_for("dms_course", institution_slug=institution_slug), status_code=303)

        success, errors = cm.handle_post_list(action, data)
        if success:
            return RedirectResponse(url=request.url_for("dms_course", institution_slug=institution_slug), status_code=303)
        form_data = data

    ctx = cm.get_list_context()
    edit_id = request.query_params.get("edit")
    ctx.update({
        "institution": institution,
        "is_academic_admin": access.can_manage_academics(),
        "editing_course": session.get(Course, int(edit_id)) if edit_id else None,
        "errors": errors,
        "form_data": form_data,
    })
    return await TemplateResponse.render("dms/course.html", request, session, ctx)


# Mosque alias
@router.get("/{institution_slug}/programs/", response_class=HTMLResponse, name="program_list")
async def programs_list(request: Request, institution_slug: str,
                        session: Session = Depends(get_session),
                        current_user: User = Depends(get_current_user)):
    return await courses_page(request, institution_slug, session, current_user)


# ── 2. Course Detail ────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/course/{course_id}/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="dms_course_detail")
async def course_detail(
    request: Request, institution_slug: str, course_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    course_obj = session.get(Course, course_id)
    if not course_obj or course_obj.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Course not found")

    cm = CourseLogic(session, current_user, target=course_obj)
    errors = None

    if request.method == "POST":
        form_data_raw = await request.form()
        data = dict(form_data_raw)
        action = data.get("action")

        if action == "delete":
            cm.delete_course(course_id)
            return RedirectResponse(url=request.url_for("dms_course", institution_slug=institution_slug), status_code=303)

        success, msg, _ = cm.handle_post_detail(action, data, form_data=form_data_raw)
        if success:
            return RedirectResponse(
                url=request.url_for("dms_course_detail", institution_slug=institution_slug, course_id=course_id),
                status_code=303
            )
        errors = {"logic": msg}

    ctx = cm.get_full_detail_context()
    ctx.update({
        "institution": institution,
        "is_academic_admin": access.can_manage_academics(),
        "errors": errors,
    })
    return await TemplateResponse.render("dms/course_detail.html", request, session, ctx)


# Mosque alias
@router.get("/{institution_slug}/programs/{course_id}/", response_class=HTMLResponse, name="program_detail")
async def program_detail(request: Request, institution_slug: str, course_id: int,
                         session: Session = Depends(get_session),
                         current_user: User = Depends(get_current_user)):
    return await course_detail(request, institution_slug, course_id, session, current_user)


# ── 3. Generate Sessions (Single Course) ───────────────────────────────────
@router.post("/{institution_slug}/course/{course_id}/generate-sessions/",
             name="course_generate_sessions")
async def generate_course_sessions(
    request: Request, institution_slug: str, course_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    from datetime import date
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    course = session.get(Course, course_id)
    if not course or course.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Course not found.")

    cm = CourseLogic(session, current_user, target=course)
    data = dict(await request.form())

    try:
        from_date = date.fromisoformat(data["from_date"]) if data.get("from_date") else None
        to_date = date.fromisoformat(data["to_date"]) if data.get("to_date") else None
    except ValueError:
        from_date = to_date = None

    result = cm.generate_sessions_from_timetable(from_date=from_date, to_date=to_date)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["created"] > 0 else "amber"
        html = (
            f"<div class='p-3 rounded-xl bg-{color}-500/10 border border-{color}-500/20 "
            f"text-{color}-400 text-sm font-bold'>"
            f"<i class='fas fa-check-circle ml-1'></i> {result['message']}"
            f"<span class='block text-xs opacity-70 mt-1'>{result.get('date_range','')}</span></div>"
        )
        resp = HTMLResponse(content=html)
        resp.headers["HX-Trigger"] = json.dumps({"sessionsGenerated": None, "refreshSessions": None})
        return resp

    return RedirectResponse(
        url=request.url_for("dms_course_detail", institution_slug=institution_slug, course_id=course_id),
        status_code=303
    )


# ── 4. Generate Sessions (All Courses Today) ───────────────────────────────
@router.post("/{institution_slug}/generate-sessions/today/",
             name="generate_all_sessions_today")
async def generate_all_sessions_today(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    result = CourseLogic.generate_today_sessions_for_institution(session, institution, current_user)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["total_created"] > 0 else "amber"
        details = "".join(f"<div class='text-xs opacity-70'>{d}</div>" for d in result.get("details", []))
        html = (
            f"<div class='p-4 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400'>"
            f"<div class='font-bold text-sm mb-1'><i class='fas fa-magic ml-1'></i> {result['message']}</div>"
            f"{details}</div>"
        )
        resp = HTMLResponse(content=html)
        resp.headers["HX-Trigger"] = json.dumps({"allSessionsGenerated": None})
        return resp

    return RedirectResponse(
        url=request.url_for("dashboard", institution_slug=institution_slug),
        status_code=303
    )
