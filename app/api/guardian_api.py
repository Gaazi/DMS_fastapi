from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session
from typing import Optional

# Internal Imports
from ..db.session import get_session
from ..models import User, Institution
from ..logic.auth import get_current_user
from ..logic.guardian import GuardianManager
from ..logic.permissions import get_institution_with_access
from ..helper.context import TemplateResponse

router = APIRouter()

# --- 1. Parent Dashboard ---
@router.get("/{institution_slug}/parent/dashboard/", response_class=HTMLResponse, name="parent_dashboard")
async def parent_dashboard(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """والدین کا ڈیش بورڈ (ان کے بچوں کی حالتِ حاضری اور فیس کی تفصیلات)۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='any')
    gm = GuardianManager(session, current_user, institution=institution)
    
    context = gm.get_dashboard_context()
    context.update({"institution": institution})
    
    return await TemplateResponse.render("dms/parent_dashboard.html", request, session, context)

# --- 2. My Students List ---
@router.get("/{institution_slug}/parent/students/", response_class=HTMLResponse, name="parent_students")
async def parent_students(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """والدین سے جڑے طالب علموں کی فہرست۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='any')
    gm = GuardianManager(session, current_user, institution=institution)
    
    context = gm.get_dashboard_context()
    return await TemplateResponse.render("dms/student_list.html", request, session, {
        "institution": institution,
        "students": context.get('students', [])
    })
