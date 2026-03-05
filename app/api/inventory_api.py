from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional

# Internal Imports
from app.core.database import get_session
from app.models import User, Institution
from app.logic.auth import get_current_user
from app.logic.inventory import InventoryManager
from app.logic.permissions import get_institution_with_access

from app.utils.context import TemplateResponse
from datetime import date as dt_date

router = APIRouter()

# --- 1. inventory_dashboard ---
@router.api_route("/{institution_slug}/inventory/", methods=["GET", "POST"], name="inventory_dashboard")
async def inventory_dashboard(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """انوینٹری اور لائبریری کا مرکزی صفحہ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    im = InventoryManager(session, current_user, institution=institution)
    from app.schemas.forms import InventoryItemSchema
    from pydantic import ValidationError
    
    errors = None
    form_data = None

    if request.method == "POST":
        raw_form = await request.form()
        form_data = dict(raw_form)
        try:
            validated = InventoryItemSchema(**form_data)
            im.save_item(validated.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
        
    context = im.get_inventory_context()
    context.update({"request": request, "institution": institution, "errors": errors, "form_data": form_data})
    return await TemplateResponse.render('dms/inventory_list.html', request, session, context)

# --- 2. issue_item ---
@router.post("/{institution_slug}/inventory/issue/", name="inventory_issue")
async def issue_item_route(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """سامان یا کتاب جاری کرنے کا عمل۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    im = InventoryManager(session, current_user, institution=institution)
    from app.schemas.forms import InventoryIssueSchema
    from pydantic import ValidationError
    
    raw_form = await request.form()
    form_data = dict(raw_form)
    
    try:
        validated = InventoryIssueSchema(**form_data)
        im.issue_item(
            item_id=validated.item_id, 
            student_id=validated.student_id, 
            staff_id=validated.staff_id, 
            quantity=validated.quantity, 
            due_date=validated.due_date
        )
        return RedirectResponse(url=request.url_for("inventory_dashboard", institution_slug=institution_slug), status_code=303)
    except ValidationError as e:
        errors = {err['loc'][0]: err['msg'] for err in e.errors()}
        context = im.get_inventory_context()
        context.update({"request": request, "institution": institution, "errors": errors, "form_data": form_data, "active_tab": "issue"})
        return await TemplateResponse.render('dms/inventory_list.html', request, session, context)

# --- 3. return_item ---
@router.post("/{institution_slug}/inventory/return/{issue_id}/", name="inventory_return")
async def return_item_route(institution_slug: str, issue_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """سامان کی واپسی درج کرنا۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    im = InventoryManager(session, current_user, institution=institution)
    im.return_item(issue_id)
    return RedirectResponse(url=f"/{institution_slug}/inventory/", status_code=303)

