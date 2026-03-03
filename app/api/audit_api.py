from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from typing import Optional

# Internal Imports
from app.db.session import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.audit import AuditManager
from app.logic.permissions import get_institution_with_access

router = APIRouter()
from app.helper.context import TemplateResponse

# --- 1. Activity Logs Overview ---

@router.get("/{institution_slug}/logs/", response_class=HTMLResponse, name="audit_logs")
async def audit_logs(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """ادارے کی تمام سرگرمیوں (Activity Logs) کا مکمل ریکارڈ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    
    am = AuditManager(current_user, session, institution=institution)
    logs = am.get_logs()
    
    return await TemplateResponse.render("dms/audit_logs.html", request, session, {
        "institution": institution,
        "logs": logs
    })

# --- 2. Recycle Bin (GET & POST) ---

@router.get("/{institution_slug}/trash/", response_class=HTMLResponse, name="recycle_bin")
async def recycle_bin_view(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """حذف شدہ آئٹمز (Soft Deleted) کی فہرست۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    
    am = AuditManager(current_user, session, institution=institution)
    trash_items = am.get_trash_items()
    
    return await TemplateResponse.render("dms/recycle_bin.html", request, session, {
        "institution": institution,
        "trash_items": trash_items
    })

@router.post("/{institution_slug}/trash/", name="recycle_bin_actions")
async def recycle_bin_actions(
    institution_slug: str,
    action: str = Form(...),
    model_path: str = Form(...),
    object_id: int = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """ری سائیکل بن سے ڈیٹا بحال کرنا یا ہمیشہ کے لیے حذف کرنا۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    am = AuditManager(current_user, session, institution=institution)
    
    if action == "restore":
        success, message = am.restore_item(model_path, object_id)
    elif action == "delete_permanent":
        success, message = am.permanent_delete(model_path, object_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid action.")

    return RedirectResponse(url=f"/{institution_slug}/trash/", status_code=303)

