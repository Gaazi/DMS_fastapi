from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session
from typing import Optional

# Internal Imports
from app.db.session import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.global_logic import GlobalManager
from app.helper.context import TemplateResponse

router = APIRouter()

# --- 1. Global Overview ---
@router.get("/global/dashboard/", response_class=HTMLResponse, name="global_dashboard")
async def global_dashboard(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """تمام متعلقہ اداروں کا مجموعی مالیاتی اور انتظامی خلاصہ (Global Overview)۔"""
    gm = GlobalManager(current_user, session)
    context = gm.get_global_overview()
    context.update({"request": request})
    
    return await TemplateResponse.render("dms/global_dashboard.html", request, session, context)

# --- 2. Institutions by Type ---
@router.get("/global/list/{institution_type}/", response_class=HTMLResponse, name="global_type_list")
async def global_type_list(request: Request, institution_type: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """مخصوص قسم (مثلاً اسکول، کالج، مدرسہ) کے تمام اداروں کی فہرست۔"""
    gm = GlobalManager(current_user, session)
    context = gm.get_type_list_context(institution_type)
    context.update({"request": request})
    
    return await TemplateResponse.render("dms/global_type_list.html", request, session, context)
