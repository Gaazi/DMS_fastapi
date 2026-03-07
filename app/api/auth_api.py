"""
Auth API — Thin Routes
──────────────────────
Login, Logout, Signup, Institution Setup, Portal Account Creation.
تمام business logic app/logic/auth.py اور app/logic/institution.py میں ہے۔
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, update

from app.core.database import get_session
from app.core.config import settings
from app.models import User, Institution, Staff, Student, Parent
from app.logic.auth import (
    UserLogic,
    get_current_user,
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token,
)
from app.logic.permissions import get_institution_with_access
from app.utils.context import TemplateResponse

router = APIRouter()


# ── 1. Welcome / Institution Setup ──────────────────────────────────────────
@router.api_route("/welcome/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="no_institution_linked")
async def no_institution_linked(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """لاگ ان یوزر جس کا کوئی ادارہ نہیں یا منظوری باقی ہے۔"""
    from app.schemas.forms import SetupInstitutionSchema
    from pydantic import ValidationError

    insts = UserLogic.get_user_institutions(current_user, session)

    if insts:
        approved = next((i for i in insts if i.is_approved), None)
        if approved:
            return RedirectResponse(url=f"/{approved.slug}/", status_code=303)
        return await TemplateResponse.render("no_institution_linked.html", request, session, {
            "pending": True, "institution": insts[0]
        })

    if request.method == "POST":
        data = dict(await request.form())
        try:
            validated = SetupInstitutionSchema(**data)
            new_inst = Institution(
                user_id=current_user.id,
                name=validated.name,
                slug=validated.slug or validated.name.lower().replace(" ", "-"),
                type=validated.type,
                is_approved=False,
            )
            session.add(new_inst)
            session.commit()
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("no_institution_linked.html", request, session, {
                "errors": errors, "form_data": data
            })

    return await TemplateResponse.render("no_institution_linked.html", request, session, {"form": None})


# ── 2. Logout ────────────────────────────────────────────────────────────────
@router.get("/logout/", name="dms_logout")
async def dms_logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response

@router.get("/{institution_slug}/logout/", name="institution_logout")
async def institution_logout(request: Request, institution_slug: str):
    return await dms_logout(request)


# ── 3. Login ─────────────────────────────────────────────────────────────────
@router.api_route("/login/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="dms_login")
async def dms_login(
    request: Request,
    session: Session = Depends(get_session),
):
    from app.schemas.forms import LoginFormSchema
    from pydantic import ValidationError

    next_url = request.query_params.get("next", "")
    reset_success = request.query_params.get("reset") == "success"

    if request.method == "POST":
        data = dict(await request.form())
        next_url = (data.get("next") or next_url or "").strip()
        try:
            validated = LoginFormSchema(**data)
            user = UserLogic.authenticate(validated.username, validated.password, session)
            if user:
                token = create_access_token({"sub": user.username})
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    redirect_url = next_url
                else:
                    default_inst = session.exec(
                        select(Institution).where(
                            Institution.user_id == user.id,
                            Institution.is_default == True
                        )
                    ).first()
                    redirect_url = (f"/{default_inst.slug}/" if default_inst
                                    else UserLogic.get_post_login_redirect(user, session))
                response = RedirectResponse(url=redirect_url, status_code=303)
                response.set_cookie(
                    key="session_token", value=token, httponly=True,
                    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                )
                return response
            return await TemplateResponse.render("login.html", request, session, {
                "error": "غلط صارف نام یا پاس ورڈ۔", "form_data": data, "errors": {}, "next": next_url
            })
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("login.html", request, session, {
                "errors": errors, "form_data": data, "error": None, "next": next_url
            })

    return await TemplateResponse.render("login.html", request, session, {
        "form": None,
        "errors": {},
        "error": None,
        "form_data": None,
        "next": next_url,
        "success": "Password reset ho gaya hai. Ab naya password se login karein." if reset_success else None,
    })

@router.api_route("/{institution_slug}/login/", methods=["GET", "POST"], name="institution_login")
async def institution_login(request: Request, institution_slug: str, session: Session = Depends(get_session)):
    return await dms_login(request, session)


# ── 4. Signup ─────────────────────────────────────────────────────────────────
# Password Reset
@router.api_route("/password-reset", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_request_no_slash")
@router.api_route("/password-reset/", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_request")
async def password_reset_request(
    request: Request,
    session: Session = Depends(get_session),
):
    from app.schemas.forms import PasswordResetRequestSchema
    from pydantic import ValidationError

    institution_slug = request.path_params.get("institution_slug")
    request_path = f"/{institution_slug}/password-reset/" if institution_slug else "/password-reset/"
    otp_verify_path_base = f"/{institution_slug}/password-reset/verify/" if institution_slug else "/password-reset/verify/"
    confirm_path_base = f"/{institution_slug}/password-reset/confirm/" if institution_slug else "/password-reset/confirm/"

    if request.method == "POST":
        data = dict(await request.form())
        try:
            validated = PasswordResetRequestSchema(**data)
            user = UserLogic.get_user_for_password_reset(validated.login, session)
            if not user:
                return await TemplateResponse.render("forgot_password.html", request, session, {
                    "errors": {},
                    "error": "Username/Email ghalat hai ya account me email save nahi hai.",
                    "form_data": data
                })

            otp = UserLogic.generate_reset_otp()
            token = create_password_reset_token(user.username, otp=otp)

            otp_verify_path = f"{otp_verify_path_base}?token={token}"
            confirm_path = f"{confirm_path_base}?token={token}"
            base_url = str(request.base_url).rstrip("/")
            otp_verify_link = f"{base_url}{otp_verify_path}"
            confirm_link = f"{base_url}{confirm_path}"

            sent, message = UserLogic.send_password_reset_email(
                to_email=user.email,
                username=user.username,
                otp=otp,
                confirm_link=confirm_link,
                otp_link=otp_verify_link,
                expire_minutes=20,
            )
            if not sent:
                return await TemplateResponse.render("forgot_password.html", request, session, {
                    "errors": {},
                    "error": message,
                    "form_data": data
                })

            return RedirectResponse(url=otp_verify_path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("forgot_password.html", request, session, {
                "errors": errors, "form_data": data, "error": None
            })

    return await TemplateResponse.render("forgot_password.html", request, session, {
        "form": None,
        "errors": {},
        "error": None,
        "form_data": None,
        "request_path": request_path,
    })


@router.api_route("/{institution_slug}/password-reset", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_request_no_slash")
@router.api_route("/{institution_slug}/password-reset/", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_request")
async def institution_password_reset_request(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
):
    return await password_reset_request(request, session)


@router.api_route("/password-reset/verify", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_verify_otp_no_slash")
@router.api_route("/password-reset/verify/", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_verify_otp")
async def password_reset_verify_otp(
    request: Request,
    session: Session = Depends(get_session),
):
    from app.schemas.forms import PasswordResetOtpSchema
    from pydantic import ValidationError

    institution_slug = request.path_params.get("institution_slug")
    request_path = f"/{institution_slug}/password-reset/" if institution_slug else "/password-reset/"
    otp_verify_path_base = f"/{institution_slug}/password-reset/verify/" if institution_slug else "/password-reset/verify/"
    confirm_path_base = f"/{institution_slug}/password-reset/confirm/" if institution_slug else "/password-reset/confirm/"

    token = request.query_params.get("token", "")
    if request.method == "POST":
        data = dict(await request.form())
        token = data.get("token", "")
        try:
            validated = PasswordResetOtpSchema(**data)
            username = verify_password_reset_token(token, otp=validated.otp)
            if not username:
                return await TemplateResponse.render("password_reset_verify_otp.html", request, session, {
                    "errors": {},
                    "error": "OTP invalid ya expired hai.",
                    "form_data": data,
                    "token": token,
                    "request_path": request_path,
                })
            return RedirectResponse(url=f"{confirm_path_base}?token={token}", status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("password_reset_verify_otp.html", request, session, {
                "errors": errors,
                "form_data": data,
                "error": None,
                "token": token,
                "request_path": request_path,
            })

    if not verify_password_reset_token(token):
        return RedirectResponse(url=request_path, status_code=303)

    return await TemplateResponse.render("password_reset_verify_otp.html", request, session, {
        "form": None,
        "errors": {},
        "error": None,
        "form_data": None,
        "token": token,
        "request_path": request_path,
        "otp_verify_path": otp_verify_path_base,
    })


@router.api_route("/{institution_slug}/password-reset/verify", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_verify_otp_no_slash")
@router.api_route("/{institution_slug}/password-reset/verify/", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_verify_otp")
async def institution_password_reset_verify_otp(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
):
    return await password_reset_verify_otp(request, session)


@router.api_route("/password-reset/confirm", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_confirm_no_slash")
@router.api_route("/password-reset/confirm/", methods=["GET", "POST"], response_class=HTMLResponse, name="password_reset_confirm")
async def password_reset_confirm(
    request: Request,
    session: Session = Depends(get_session),
):
    from app.schemas.forms import PasswordResetConfirmSchema
    from pydantic import ValidationError

    institution_slug = request.path_params.get("institution_slug")
    request_path = f"/{institution_slug}/password-reset/" if institution_slug else "/password-reset/"
    login_path = f"/{institution_slug}/login/?reset=success" if institution_slug else "/login/?reset=success"

    token = request.query_params.get("token", "")
    if request.method == "POST":
        data = dict(await request.form())
        token = data.get("token", "")
        try:
            validated = PasswordResetConfirmSchema(**data)
            username = verify_password_reset_token(token)
            if not username:
                return await TemplateResponse.render("reset_password.html", request, session, {
                    "errors": {},
                    "error": "Reset link is invalid or expired.",
                    "form_data": data,
                    "token": token,
                    "request_path": request_path,
                })

            user = session.exec(select(User).where(User.username == username)).first()
            if not user:
                return await TemplateResponse.render("reset_password.html", request, session, {
                    "errors": {},
                    "error": "Reset link is invalid or expired.",
                    "form_data": data,
                    "token": token,
                    "request_path": request_path,
                })

            UserLogic.set_new_password(user, validated.password, session)
            return RedirectResponse(url=login_path, status_code=303)
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("reset_password.html", request, session, {
                "errors": errors,
                "form_data": data,
                "error": None,
                "token": token,
                "request_path": request_path,
            })

    if not verify_password_reset_token(token):
        return RedirectResponse(url=request_path, status_code=303)

    return await TemplateResponse.render("reset_password.html", request, session, {
        "form": None,
        "errors": {},
        "error": None,
        "form_data": None,
        "token": token,
        "request_path": request_path,
    })


@router.api_route("/{institution_slug}/password-reset/confirm", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_confirm_no_slash")
@router.api_route("/{institution_slug}/password-reset/confirm/", methods=["GET", "POST"], response_class=HTMLResponse, name="institution_password_reset_confirm")
async def institution_password_reset_confirm(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
):
    return await password_reset_confirm(request, session)

@router.api_route("/{institution_slug}/profile/change-password/", methods=["GET", "POST"], response_class=HTMLResponse, name="change_password")
async def change_password(
    request: Request,
    institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url=f"/{institution_slug}/login/", status_code=303)
        
    from app.schemas.forms import ChangePasswordSchema
    from pydantic import ValidationError

    ctx = {"institution_slug": institution_slug, "user": current_user, "form_data": None, "errors": {}, "error": None, "success": None}

    if request.method == "POST":
        data = dict(await request.form())
        ctx["form_data"] = data
        try:
            validated = ChangePasswordSchema(**data)
            is_valid = UserLogic.verify_password(validated.current_password, current_user.password)
            if not is_valid:
                ctx["error"] = "Mawjooda password ghalat hai."
                return await TemplateResponse.render("change_password.html", request, session, ctx)

            UserLogic.set_new_password(current_user, validated.new_password, session)
            ctx["success"] = "Password kamyabe se tabdeel ho gaya hai."
            ctx["form_data"] = None
        except ValidationError as e:
            ctx["errors"] = {err["loc"][0]: err["msg"] for err in e.errors()}

    return await TemplateResponse.render("change_password.html", request, session, ctx)

@router.api_route("/signup/", methods=["GET", "POST"],
                  response_class=HTMLResponse, name="dms_signup")
async def signup(
    request: Request,
    session: Session = Depends(get_session),
):
    from app.schemas.forms import SignupFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        data = dict(await request.form())
        try:
            validated = SignupFormSchema(**data)
            success, message, _ = UserLogic.handle_signup(validated.dict(), session)
            if success:
                return RedirectResponse(url="/welcome/", status_code=303)
            return await TemplateResponse.render("signup.html", request, session, {"error": message, "form_data": data})
        except ValidationError as e:
            errors = {err["loc"][0]: err["msg"] for err in e.errors()}
            return await TemplateResponse.render("signup.html", request, session, {"errors": errors, "form_data": data})

    return await TemplateResponse.render("signup.html", request, session, {"form": None})


# ── 5. Set Default Institution ───────────────────────────────────────────────
@router.get("/account/set-default/{institution_slug}/", name="set_default_institution")
async def set_default_institution(
    request: Request, institution_slug: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    inst = session.exec(
        select(Institution).where(
            Institution.slug == institution_slug,
            Institution.user_id == current_user.id
        )
    ).first()
    if not inst:
        raise HTTPException(status_code=404)
    session.execute(update(Institution).where(Institution.user_id == current_user.id).values(is_default=False))
    inst.is_default = True
    session.add(inst)
    session.commit()
    return RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)


# ── 6. Create Portal Account ─────────────────────────────────────────────────
@router.post("/{institution_slug}/account/create/{person_type}/{person_id}/",
             name="create_portal_account")
async def create_portal_account(
    request: Request, institution_slug: str, person_type: str, person_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    institution, _ = get_institution_with_access(institution_slug, session, current_user, access_type="admin")
    model_map = {"staff": Staff, "student": Student, "parent": Parent}
    model = model_map.get(person_type)
    if not model:
        raise HTTPException(status_code=400, detail="Invalid person type")

    person = session.get(model, person_id)
    if not person or person.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Not found")

    if not person.user_id:
        try:
            UserLogic.ensure_user(person, prefix=person_type, session=session)
            session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return RedirectResponse(url=request.headers.get("referer", f"/{institution_slug}/"), status_code=303)


# ── 7. Google Auth Placeholder ───────────────────────────────────────────────
@router.get("/auth/google/", name="auth_google")
async def auth_google(request: Request, process: str = "login"):
    return RedirectResponse(url="/login/", status_code=303)

