"""
Facility API — Thin Routes
───────────────────────────
تمام business logic app/logic/facilities.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.database import get_session
from app.models import User
from app.logic.auth import get_current_user
from app.logic.facilities import FacilityLogic
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse
from sqlmodel import Session

router = APIRouter()


# ── 1. Facility List ─────────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/facilities", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="facility_list")
async def facility_list(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    fm = FacilityLogic(session, current_user, institution=institution)
    errors = None

    if request.method == "POST":
        from app.schemas.forms import FacilityFormSchema
        from pydantic import ValidationError
        data = dict(await request.form())
        action = data.get("action")

        if action == "delete":
            fm.delete_facility(int(data.get("id", 0)))
            if request.headers.get("HX-Request"):
                return HTMLResponse(status_code=204)
        else:
            try:
                validated = FacilityFormSchema(**data)
                fm.save_facility(validated.dict())
                return RedirectResponse(url=request.url.path, status_code=303)
            except ValidationError as e:
                errors = {err["loc"][0]: err["msg"] for err in e.errors()}

    edit_id = request.query_params.get("edit_id")
    ctx = fm.get_list_context(edit_id=int(edit_id) if edit_id else None)
    ctx.update({"institution": institution, "errors": errors})
    return await TemplateResponse.render("dms/facility_list.html", request, session, ctx)
