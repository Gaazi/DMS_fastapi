"""
Inventory API — Thin Routes
────────────────────────────
تمام business logic app/logic/inventory.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.inventory import InventoryLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Inventory Dashboard ───────────────────────────────────────────────────
@router.api_route("/{institution_slug}/inventory/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="inventory_dashboard")
async def inventory_dashboard(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    im = InventoryLogic(session, current_user, institution=institution)
    errors = None

    if request.method == "POST":
        from app.schemas.forms import InventoryItemSchema
        from pydantic import ValidationError
        data = dict(await request.form())
        try:
            validated = InventoryItemSchema(**data)
            im.save_item(validated.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}

    ctx = im.get_inventory_context()
    ctx.update({
        "institution": institution, 
        "errors": errors, 
        "form_data": data if request.method == "POST" else {}
    })
    return await TemplateResponse.render("dms/inventory_list.html", request, session, ctx)


# ── 2. Issue Item ────────────────────────────────────────────────────────────
@router.post("/{institution_slug}/inventory/issue/", name="inventory_issue")
async def issue_item(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    im = InventoryLogic(session, current_user, institution=institution)

    from app.schemas.forms import InventoryIssueSchema
    from pydantic import ValidationError
    data = dict(await request.form())
    try:
        v = InventoryIssueSchema(**data)
        im.issue_item(item_id=v.item_id, student_id=v.student_id,
                      staff_id=v.staff_id, quantity=v.quantity, due_date=v.due_date)
        return RedirectResponse(
            url=request.url_for("inventory_dashboard", institution_slug=institution_slug),
            status_code=303
        )
    except ValidationError as e:
        errors = {err["loc"][0]: err["msg"] for err in e.errors()}
        ctx = im.get_inventory_context()
        ctx.update({"institution": institution, "errors": errors, "active_tab": "issue"})
        return await TemplateResponse.render("dms/inventory_list.html", request, session, ctx)


# ── 3. Return Item ───────────────────────────────────────────────────────────
@router.post("/{institution_slug}/inventory/return/{issue_id}/", name="inventory_return")
async def return_item(
    institution_slug: str, issue_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    InventoryLogic(session, current_user, institution=institution).return_item(issue_id)
    return RedirectResponse(url=f"/{institution_slug}/inventory/", status_code=303)
