"""
Base API — Thin Routes
──────────────────────
Dashboard, Institution Settings, Admin Tools, PWA, etc.
تمام business logic app/logic/institution.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlmodel import Session
from typing import Optional

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.institution import InstitutionLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Home (Public Landing) ────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse, name="dms")
async def home(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    ctx = InstitutionLogic.get_home_stats(session)
    # ماہانہ fee auto-generate (15 تاریخ کے بعد)
    from datetime import datetime
    if datetime.now().day >= 15:
        from app.logic.finance import FinanceLogic
        background_tasks.add_task(FinanceLogic.run_global_monthly_generation, session)
    return await TemplateResponse.render("dms/dms.html", request, session, ctx)


# ── 2. Smart Redirect ────────────────────────────────────────────────────────
@router.get("/go/{institution_slug}", name="smart_redirect")
async def smart_redirect(
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    url = InstitutionLogic.get_smart_redirect(institution_slug, current_user, session)
    return RedirectResponse(url=url, status_code=303)


# ── 3. Dashboard ────────────────────────────────────────────────────────────
@router.get("/{institution_slug}/", response_class=HTMLResponse, name="dashboard")
async def dashboard(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    im = InstitutionLogic(current_user, session=session, institution=institution)
    ctx = im.get_dashboard_data()
    return await TemplateResponse.render("dms/dashboard.html", request, session, ctx)

# ── 3.1 All Notifications ────────────────────────────────────────────────────
@router.get("/{institution_slug}/all-notifications/", response_class=HTMLResponse, name="all_notifications")
async def all_notifications(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="any")
    
    # Generate some notifications using alerts
    im = InstitutionLogic(current_user, session=session, institution=institution)
    alerts = im.get_quick_alerts()
    
    notifications = []
    if alerts.get('count', 0) > 0:
        for student in alerts.get('defaulters', []):
            notifications.append({
                "title": "فیس کی ادائیگی زیر التوا",
                "description": f"طالب علم {student.name} کی دو یا اس سے زیادہ فیسیں واجب الادا ہیں۔",
                "time": "آج",
                "color": "rose",
                "icon": "fa-solid fa-triangle-exclamation",
                "url": request.url_for("student_detail", institution_slug=institution.slug, student_id=student.id)
            })
        for course in alerts.get('full_classes', []):
            notifications.append({
                "title": "کلاس تقریباً بھر چکی ہے",
                "description": f"کورس {course.name} کی گنجائش پوری ہونے کے قریب ہے۔",
                "time": "آج",
                "color": "amber",
                "icon": "fa-solid fa-users",
                "url": request.url_for("course_detail", institution_slug=institution.slug, course_id=course.id)
            })
            
    # Add system notification
    notifications.append({
        "title": "DMS سسٹم میں خوش آمدید",
        "description": "پروجیکٹ ڈیٹا مکمل طور پر ہم آہنگ ہے۔",
        "time": "سسٹم",
        "color": "indigo",
        "icon": "fa-solid fa-check-circle",
        "url": "#"
    })
    
    return await TemplateResponse.render("dms/all_notifications.html", request, session, {
        "institution": institution,
        "notifications": notifications
    })


# ── 4. Institution Overview (تمام ادارے) ────────────────────────────────────
@router.get("/overview/", response_class=HTMLResponse, name="institution_overview")
@router.get("/overview/{institution_type}/", response_class=HTMLResponse, name="institution_type_list")
async def institution_overview(
    request: Request,
    institution_type: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    from app.logic.auth import UserLogic
    insts = UserLogic.get_user_institutions(current_user, session)
    if institution_type:
        insts = [i for i in insts if i.type == institution_type]
    return await TemplateResponse.render("dms/institution_overview.html", request, session, {"institutions": insts})


# ── 5. Institution Detail ────────────────────────────────────────────────────
@router.get("/{institution_slug}/details/", response_class=HTMLResponse, name="institution_detail")
async def institution_detail(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    return await TemplateResponse.render("dms/institution_settings.html", request, session, {"institution": institution})


# ── 6. Manage Accounts ───────────────────────────────────────────────────────
@router.get("/{institution_slug}/accounts-manager/", response_class=HTMLResponse, name="manage_accounts")
async def manage_accounts(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    return await TemplateResponse.render("dms/manage_accounts.html", request, session, {"institution": institution})


# ── 7. Settings ──────────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/settings/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="institution_settings")
async def settings(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    im = InstitutionLogic(current_user, session=session, institution=institution)
    errors = None

    if request.method == "POST":
        from app.schemas.forms import InstitutionSettingsSchema
        from pydantic import ValidationError
        data = dict(await request.form())
        try:
            validated = InstitutionSettingsSchema(**data)
            im.update_settings(validated.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("dms/institution_settings.html", request, session, {
                "institution": institution, "errors": errors, "form_data": data
            })

    return await TemplateResponse.render("dms/institution_settings.html", request, session, {"institution": institution})


# ── 8. Admin Tools ───────────────────────────────────────────────────────────
@router.get("/{institution_slug}/admin-tools/", response_class=HTMLResponse, name="institution_admin_tools")
async def admin_tools_view(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    return await TemplateResponse.render("dms/tools.html", request, session, {"institution": institution})


@router.post("/{institution_slug}/admin-tools/", name="institution_admin_tools_post")
async def admin_tools_post(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    data = dict(await request.form())
    if data.get("action") == "bulk_update":
        InstitutionLogic(current_user, session, institution).run_bulk_maintenance()
    return RedirectResponse(url=request.url.path, status_code=303)


# ── 9. Superadmin Overview ───────────────────────────────────────────────────
@router.get("/superadmin/overview", response_class=HTMLResponse, name="superadmin_overview")
async def superadmin_overview(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_superuser:
        raise HTTPException(status_code=403)
    from sqlmodel import select
    from app.models import Institution
    institutions = session.exec(select(Institution)).all()
    return await TemplateResponse.render("dms/superadmin_overview.html", request, session, {"institutions": institutions})


# ── 10. PWA & Static Assets ──────────────────────────────────────────────────
@router.get("/manifest.json",     name="manifest")
async def manifest():
    return FileResponse("static/manifest.json")

@router.get("/service-worker.js", name="service_worker")
async def service_worker():
    return FileResponse("static/service-worker.js")

@router.get("/share-target/",     name="share_target")
async def share_target():
    return RedirectResponse(url="/", status_code=302)


# ── 12. Smart Shortcut ───────────────────────────────────────────────────────
@router.get("/shortcut/{action}/", name="smart_shortcut")
async def smart_shortcut(action: str, current_user: User = Depends(get_current_user)):
    return RedirectResponse(url="/", status_code=302)


# ── 13. System Backup Manager (Superadmin) ───────────────────────────────────
@router.get("/system/backup/", response_class=HTMLResponse, name="system_backup_manager")
async def system_backup_manager(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_superuser:
        raise HTTPException(status_code=403)
    return await TemplateResponse.render("dms/backup_manager.html", request, session)
