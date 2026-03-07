"""
Guardian/Parent API — Thin Routes
───────────────────────────────────
تمام business logic app/logic/guardian.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.guardian import GuardianLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Parent Dashboard ──────────────────────────────────────────────────────
@router.get("/{institution_slug}/parent/dashboard/",
            response_class=HTMLResponse, name="parent_dashboard")
async def parent_dashboard(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    gm = GuardianLogic(session, current_user, institution=institution)
    ctx = gm.get_dashboard_context()
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/parent_dashboard.html", request, session, ctx)


# ── 1.1 Guardian Dashboard (Django alias) ────────────────────────────────────
@router.get("/{institution_slug}/guardian/",
            response_class=HTMLResponse, name="guardian_dashboard_scoped")
async def guardian_dashboard_scoped(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    gm = GuardianLogic(session, current_user, institution=institution)
    ctx = gm.get_dashboard_context()
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/parent_dashboard.html", request, session, ctx)


# ── 2. Parent Students List ──────────────────────────────────────────────────
@router.get("/{institution_slug}/parent/students/",
            response_class=HTMLResponse, name="parent_students")
async def parent_students(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    gm = GuardianLogic(session, current_user, institution=institution)
    ctx = gm.get_dashboard_context()
    return await TemplateResponse.render("dms/student_list.html", request, session, {
        "institution": institution,
        "students": ctx.get("students", []),
    })
