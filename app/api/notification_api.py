from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session
from typing import Optional

from app.db.session import get_session
from app.models import User, Institution
from app.logic.auth import get_current_user
from app.logic.permissions import get_institution_with_access
from app.logic.sms import NotificationManager, SMSService
from app.helper.context import TemplateResponse

router = APIRouter()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _nm(institution, session, user) -> NotificationManager:
    return NotificationManager(session, institution, user)


# ─── 1. SMS Dashboard ────────────────────────────────────────────────────────

@router.get("/{institution_slug}/notifications/", response_class=HTMLResponse, name="sms_dashboard")
async def sms_dashboard(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """SMS اطلاعات کا مرکزی صفحہ"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    import os
    sms_provider = os.getenv("SMS_PROVIDER", "console")
    sms_configured = sms_provider != "console"

    context = {
        "request":        request,
        "institution":    institution,
        "sms_provider":   sms_provider,
        "sms_configured": sms_configured,
    }
    return await TemplateResponse.render("dms/sms_dashboard.html", request, session, context)


# ─── 2. غیر حاضری کی اطلاع ──────────────────────────────────────────────────

@router.post("/{institution_slug}/notifications/absent/", name="notify_absences")
async def notify_absences(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """آج کے غیر حاضر طلبہ کے والدین کو SMS"""
    import json
    from datetime import date
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    form = await request.form()
    date_str = form.get("target_date")
    try:
        target_date = date.fromisoformat(date_str) if date_str else None
    except ValueError:
        target_date = None

    nm = _nm(institution, session, current_user)
    result = nm.notify_absences_today(target_date=target_date)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["sent"] > 0 else "amber"
        html = f"""<div class='p-4 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400 text-sm'>
            <div class='font-bold mb-1'><i class='fas fa-check-circle ml-1'></i> {result['message']}</div>
            <div class='text-xs opacity-70'>بھیجے گئے: {result['sent']} | ناکام: {result['failed']} | چھوڑے: {result['skipped']}</div>
        </div>"""
        return HTMLResponse(content=html)

    return RedirectResponse(url=request.url_for("sms_dashboard", institution_slug=institution_slug), status_code=303)


# ─── 3. فیس یاد دہانی ───────────────────────────────────────────────────────

@router.post("/{institution_slug}/notifications/fees/", name="notify_fees")
async def notify_fees(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """بقایا فیس والے طلبہ کے والدین کو SMS"""
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    form = await request.form()
    overdue_only = form.get("overdue_only") == "on"

    nm = _nm(institution, session, current_user)
    result = nm.notify_pending_fees(overdue_only=overdue_only)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["sent"] > 0 else "amber"
        html = f"""<div class='p-4 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400 text-sm'>
            <div class='font-bold mb-1'><i class='fas fa-check-circle ml-1'></i> {result['message']}</div>
            <div class='text-xs opacity-70'>بھیجے گئے: {result['sent']} | ناکام: {result['failed']} | چھوڑے: {result['skipped']}</div>
        </div>"""
        return HTMLResponse(content=html)

    return RedirectResponse(url=request.url_for("sms_dashboard", institution_slug=institution_slug), status_code=303)


# ─── 4. ماہانہ خلاصہ ────────────────────────────────────────────────────────

@router.post("/{institution_slug}/notifications/monthly-summary/", name="notify_monthly_summary")
async def notify_monthly_summary(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """ماہانہ حاضری خلاصہ SMS"""
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    form = await request.form()
    try:
        month = int(form.get("month", 0)) or None
        year  = int(form.get("year", 0))  or None
    except (ValueError, TypeError):
        month = year = None

    nm = _nm(institution, session, current_user)
    result = nm.notify_monthly_summary(month=month, year=year)

    if request.headers.get("HX-Request"):
        color = "emerald" if result["sent"] > 0 else "amber"
        html = f"""<div class='p-4 rounded-xl bg-{color}-500/10 border border-{color}-500/20 text-{color}-400 text-sm'>
            <div class='font-bold mb-1'><i class='fas fa-check-circle ml-1'></i> {result['message']}</div>
            <div class='text-xs opacity-70'>بھیجے گئے: {result['sent']} | ناکام: {result['failed']} | چھوڑے: {result['skipped']}</div>
        </div>"""
        return HTMLResponse(content=html)

    return RedirectResponse(url=request.url_for("sms_dashboard", institution_slug=institution_slug), status_code=303)


# ─── 5. Custom SMS بھیجنا ───────────────────────────────────────────────────

@router.post("/{institution_slug}/notifications/custom/", name="notify_custom")
async def notify_custom(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """کسی بھی نمبر پر custom SMS بھیجنا"""
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type='admin')

    form = await request.form()
    phone   = form.get("phone", "").strip()
    message = form.get("message", "").strip()

    if not phone or not message:
        raise HTTPException(status_code=400, detail="نمبر اور پیغام ضروری ہیں۔")

    sms = SMSService()
    success = sms.send(phone, message)

    if request.headers.get("HX-Request"):
        if success:
            html = f"<div class='p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-bold'><i class='fas fa-check ml-1'></i> SMS کامیابی سے بھیج دیا گیا۔</div>"
        else:
            html = "<div class='p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm font-bold'><i class='fas fa-times ml-1'></i> SMS بھیجنے میں خرابی۔</div>"
        return HTMLResponse(content=html)

    return RedirectResponse(url=request.url_for("sms_dashboard", institution_slug=institution_slug), status_code=303)
