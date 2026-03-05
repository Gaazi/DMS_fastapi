from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import json

# Internal Imports
from app.core.database import get_session
from app.models import User, Institution
from app.logic.auth import get_current_user
from app.logic.facilities import FacilityManager
from app.logic.permissions import get_institution_with_access

from app.utils.context import TemplateResponse

router = APIRouter()

# --- 1. facility_list (Main View) ---
@router.api_route("/{institution_slug}/facilities", methods=["GET", "POST"], name="facility_list")
async def facility_list(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """سہولیات (Facilities) کی فہرست اور مینجمنٹ۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    fm = FacilityManager(session, current_user, institution=institution)
    
    from app.schemas.forms import FacilityFormSchema
    from pydantic import ValidationError
    
    errors = None
    form_data = None

    if request.method == "POST":
        raw_form = await request.form()
        form_data = dict(raw_form)
        action = form_data.get('action')
        
        if action == "delete":
            facility_id = int(form_data.get('id', 0))
            fm.delete_facility(facility_id)
            if request.headers.get('HX-Request'):
                return HTMLResponse(status_code=204)
        else:
            try:
                validated = FacilityFormSchema(**form_data)
                fm.save_facility(validated.dict())
                return RedirectResponse(url=request.url.path, status_code=303)
            except ValidationError as e:
                errors = {err['loc'][0]: err['msg'] for err in e.errors()}
    
    edit_id = request.query_params.get('edit_id')
    context = fm.get_list_context(edit_id=int(edit_id) if edit_id else None)
    context.update({"request": request, "institution": institution})
    
    return await TemplateResponse.render("dms/facility_list.html", request, session, context)

