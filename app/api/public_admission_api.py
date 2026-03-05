"""
Public Admission API — Thin Routes
────────────────────────────────────
بغیر لاگ ان عوامی داخلہ فارم۔
تمام business logic app/logic/students.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Institution
from app.utils.context import TemplateResponse

router = APIRouter()


# ── Public Admission Form ────────────────────────────────────────────────────
@router.api_route("/{institution_slug}/join/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="public_admission")
async def public_admission(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
):
    """عوامی داخلہ فارم — بغیر لاگ ان۔"""
    institution = session.exec(
        select(Institution).where(Institution.slug == institution_slug)
    ).first()
    if not institution:
        return HTMLResponse(content="ادارہ نہیں ملا۔", status_code=404)

    from app.logic.students import StudentLogic

    sm = StudentLogic(session, user=None, institution=institution)

    if request.method == "POST":
        from app.schemas.forms import PublicAdmissionSchema
        from pydantic import ValidationError
        data = dict(await request.form())
        try:
            validated = PublicAdmissionSchema(**data)
            success, message = sm.handle_public_admission(validated.dict())
            if success:
                return await TemplateResponse.render(
                    "dms/public_admission_success.html", request, session,
                    {"institution": institution}
                )
            ctx = sm.get_public_admission_context()
            ctx.update({"institution": institution, "error_msg": message})
            return await TemplateResponse.render("dms/public_admission.html", request, session, ctx)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            ctx = sm.get_public_admission_context()
            ctx.update({"institution": institution, "errors": errors, "form_data": data})
            return await TemplateResponse.render("dms/public_admission.html", request, session, ctx)

    ctx = sm.get_public_admission_context()
    ctx["institution"] = institution
    return await TemplateResponse.render("dms/public_admission.html", request, session, ctx)
