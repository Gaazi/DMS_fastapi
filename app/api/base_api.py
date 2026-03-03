from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from typing import Optional
from datetime import datetime
import json

# Internal Imports
from app.db.session import get_session
from app.models import Institution, Income, Expense, User
from app.logic.auth import get_current_user, UserManager
from app.logic.institution import InstitutionManager
from app.logic.permissions import get_institution_with_access
from app.helper.context import TemplateResponse

router = APIRouter()

# --- 1. home (جینگو کا اصل نام) ---
@router.get("/", response_class=HTMLResponse, name="dms")
async def home(request: Request, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):
    total_inst = session.exec(select(func.count(Institution.id))).one()
    income_sum = session.exec(select(func.sum(Income.amount))).one() or 0
    expense_sum = session.exec(select(func.sum(Expense.amount))).one() or 0
    
    # گلوبل آٹو میشن (15 تاریخ والا لاجک)
    now = datetime.now()
    if now.day >= 15:
        from app.logic.finance import FinanceManager
        background_tasks.add_task(FinanceManager.run_global_monthly_generation, session)

    return await TemplateResponse.render("dms/dms.html", request, session, {
        "total_institutions": total_inst,
        "total_income": income_sum,
        "total_expense": expense_sum,
        "total_balance": income_sum - expense_sum,
        "currency_label": "PKR"
    })

# --- 2. smart_redirect ---
@router.get("/go/{institution_slug}")
async def smart_redirect(institution_slug: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    if not institution: raise HTTPException(status_code=404)
    
    # Guardian/Student Redirection Logic
    if hasattr(current_user, 'student') and current_user.student and current_user.student.inst_id == institution.id:
        return RedirectResponse(url=f"/{institution_slug}/student/{current_user.student.id}", status_code=303)
    if hasattr(current_user, 'parent') and current_user.parent and current_user.parent.inst_id == institution.id:
        return RedirectResponse(url=f"/{institution_slug}/guardian", status_code=303)
        
    return RedirectResponse(url=f"/{institution_slug}/dashboard", status_code=303)

# --- 3. dashboard ---
@router.get("/{institution_slug}/", response_class=HTMLResponse, name="dashboard")
async def dashboard(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    if not institution: raise HTTPException(status_code=404)
    
    im = InstitutionManager(current_user, session=session, institution=institution)
    context = im.get_dashboard_data()
    return await TemplateResponse.render("dms/dashboard.html", request, session, context)

# --- 4. overview ---
@router.get("/overview/", response_class=HTMLResponse, name="institution_overview")
async def institution_overview(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Summary of all institutions owned by the user."""
    insts = session.exec(select(Institution).where(Institution.user_id == current_user.id)).all()
    return await TemplateResponse.render("dms/institution_overview.html", request, session, {"institutions": insts})

# --- 5. institution_detail ---
@router.get("/{institution_slug}/details/", response_class=HTMLResponse, name="institution_detail")
async def institution_detail(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    return await TemplateResponse.render("dms/institution_settings.html", request, session, {"institution": institution})

# --- 6. manage_accounts ---
@router.get("/{institution_slug}/accounts-manager/", response_class=HTMLResponse, name="manage_accounts")
async def manage_accounts(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    return await TemplateResponse.render("dms/manage_accounts.html", request, session, {"institution": institution})

# --- 7. settings ---
@router.api_route("/{institution_slug}/settings/", methods=["GET", "POST"], name="institution_settings")
async def settings(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    from app.schemas.forms import InstitutionSettingsSchema
    from pydantic import ValidationError
    
    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = InstitutionSettingsSchema(**data)
            InstitutionManager(current_user, session, institution).update_settings(validated_data.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render("dms/institution_settings.html", request, session, {
                "institution": institution, "errors": errors, "form_data": data
            })
    return await TemplateResponse.render("dms/institution_settings.html", request, session, {"institution": institution})

# --- 8. admin_tools ---
@router.get("/{institution_slug}/admin-tools/", response_class=HTMLResponse, name="institution_admin_tools")
async def admin_tools_view(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    return await TemplateResponse.render("dms/tools.html", request, session, {"institution": institution})

# --- 9. superadmin_overview ---
@router.get("/superadmin/overview", response_class=HTMLResponse, name="superadmin_overview")
async def superadmin_overview(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    institutions = session.exec(select(Institution)).all()
    return await TemplateResponse.render("dms/superadmin_overview.html", request, session, {"institutions": institutions})

# --- 10. PWA & Assets ---
@router.get("/manifest.json", name="manifest")
async def manifest():
    return FileResponse("static/manifest.json")

@router.get("/service-worker.js", name="service_worker")
async def service_worker():
    return FileResponse("static/service-worker.js")

@router.get("/share-target/", name="share_target")
async def share_target():
    return RedirectResponse(url="/", status_code=302)

# --- 11. all_notifications ---
@router.get("/{institution_slug}/notifications/", response_class=HTMLResponse, name="all_notifications")
async def all_notifications(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    return await TemplateResponse.render("dms/all_notifications.html", request, session, {"institution_slug": institution_slug})

# --- 12. smart_shortcut ---
@router.get("/shortcut/{action}/", name="smart_shortcut")
async def smart_shortcut(action: str, current_user: User = Depends(get_current_user)):
    return RedirectResponse(url="/", status_code=302)

# --- 13. system_backup_manager ---
@router.get("/system/backup/", response_class=HTMLResponse, name="system_backup_manager")
async def system_backup_manager(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(status_code=403)
    return await TemplateResponse.render("dms/backup_manager.html", request, session)
