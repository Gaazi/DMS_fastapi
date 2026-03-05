"""
Exams API — Thin Routes
────────────────────────
تمام business logic app/logic/exams.py میں ہے۔
"""
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.exams import ExamLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Exam List ─────────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/exams/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="exam_list")
async def exam_list(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    em = ExamLogic(session, current_user, institution=institution)

    errors = None

    if request.method == "POST":
        from app.schemas.forms import ExamFormSchema
        from pydantic import ValidationError
        data = dict(await request.form())
        try:
            validated = ExamFormSchema(**data)
            em.save_exam(validated.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}

    ctx = em.get_list_context()
    ctx.update({"institution": institution, "errors": errors})
    return await TemplateResponse.render("dms/exams.html", request, session, ctx)


# ── 2. Record Marks ──────────────────────────────────────────────────────────
@router.get("/{institution_slug}/exams/{exam_id}/record/",
            response_class=HTMLResponse, name="record_marks",
            operation_id="record_marks_get")
async def record_marks_get(
    request: Request, institution_slug: str, exam_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    em = ExamLogic(session, current_user, institution=institution)
    ctx = em.get_record_marks_context(exam_id)
    if not ctx:
        raise HTTPException(status_code=404)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/record_marks.html", request, session, ctx)


@router.post("/{institution_slug}/exams/{exam_id}/record/",
             name="record_marks_post", operation_id="record_marks_post")
async def record_marks_post(
    request: Request, institution_slug: str, exam_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    em = ExamLogic(session, current_user, institution=institution)
    form_data = await request.form()
    marks_raw = form_data.get("marks_json")
    if marks_raw:
        em.record_marks(json.loads(marks_raw), exam_id=exam_id)
    return RedirectResponse(url=request.url_for("exam_list", institution_slug=institution_slug), status_code=303)


# ── 3. Report Card ───────────────────────────────────────────────────────────
@router.get("/{institution_slug}/exams/{exam_id}/report/{student_id}/",
            response_class=HTMLResponse, name="report_card")
async def report_card(
    request: Request, institution_slug: str, exam_id: int, student_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="academic_view")
    em = ExamLogic(session, current_user, institution=institution)
    ctx = em.get_report_card_context(exam_id, student_id)
    if not ctx:
        raise HTTPException(status_code=404)
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/report_card.html", request, session, ctx)
