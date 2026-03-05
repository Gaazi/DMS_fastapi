"""
Global API — Thin Routes
─────────────────────────
تمام institutions کا مجموعی overview۔
تمام logic app/logic/global_logic.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.global_logic import GlobalLogic
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Global Dashboard ──────────────────────────────────────────────────────
@router.get("/global/dashboard/", response_class=HTMLResponse, name="global_dashboard")
async def global_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    gm = GlobalLogic(current_user, session)
    ctx = gm.get_global_overview()
    return await TemplateResponse.render("dms/global_dashboard.html", request, session, ctx)


# ── 2. Institutions By Type ──────────────────────────────────────────────────
@router.get("/global/list/{institution_type}/", response_class=HTMLResponse, name="global_type_list")
async def global_type_list(
    request: Request, institution_type: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    gm = GlobalLogic(current_user, session)
    ctx = gm.get_type_list_context(institution_type)
    return await TemplateResponse.render("dms/global_type_list.html", request, session, ctx)
