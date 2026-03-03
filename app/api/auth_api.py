from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, update
from typing import Optional
import json

# Internal Imports
from app.db.session import get_session
from app.models import User, Institution, Staff, Student, Parent
from app.logic.auth import UserManager, get_current_user, create_access_token
from app.logic.permissions import get_institution_with_access
from app.core.config import settings
from app.helper.context import TemplateResponse



router = APIRouter()

# --- 1. no_institution_linked ---
@router.api_route("/welcome/", methods=["GET", "POST"], response_class=HTMLResponse, name="no_institution_linked")
async def no_institution_linked(request: Request, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """جب یوزر لاگ ان ہو لیکن اس کا کوئی ادارہ نہ ہو یا منظوری کا منتظر ہو۔"""
    from app.schemas.forms import SetupInstitutionSchema
    from pydantic import ValidationError

    insts = UserManager.get_user_institutions(current_user, session)
    
    if insts:
        approved_inst = next((i for i in insts if i.is_approved), None)
        if approved_inst:
            return RedirectResponse(url=f"/{approved_inst.slug}/", status_code=303)
        else:
            return await TemplateResponse.render("no_institution_linked.html", request, session, {
                "pending": True, 
                "institution": insts[0]
            })

    if request.method == 'POST':
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = SetupInstitutionSchema(**data)
            new_inst = Institution(
                user_id=current_user.id,
                name=validated_data.name,
                slug=validated_data.slug or validated_data.name.lower().replace(' ', '-'),
                type=validated_data.type,
                is_approved=False
            )
            session.add(new_inst)
            session.commit()
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render("no_institution_linked.html", request, session, {"errors": errors, "form_data": data})

    return await TemplateResponse.render("no_institution_linked.html", request, session, {"form": None})

# --- 2. dms_logout ---
@router.get("/logout/", name="dms_logout")
async def dms_logout(request: Request):
    """لاگ آؤٹ اور ہوم پیج پر واپسی۔"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response

@router.get("/{institution_slug}/logout/", name="institution_logout")
async def institution_logout(request: Request, institution_slug: str):
    return await dms_logout(request)

# --- 3. dms_login ---
@router.api_route("/login/", methods=["GET", "POST"], response_class=HTMLResponse, name="dms_login")
async def dms_login(request: Request, session: Session = Depends(get_session)):
    """لاگ ان ویو۔"""
    from app.schemas.forms import LoginFormSchema
    from pydantic import ValidationError

    if request.method == 'POST':
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = LoginFormSchema(**data)
            user = UserManager.authenticate(validated_data.username, validated_data.password, session)
            if user:
                token = create_access_token({"sub": user.username})
                default_inst = session.exec(select(Institution).where(Institution.user_id == user.id, Institution.is_default == True)).first()
                redirect_url = f"/{default_inst.slug}/" if default_inst else UserManager.get_post_login_redirect(user)
                
                response = RedirectResponse(url=redirect_url, status_code=303)
                response.set_cookie(key="session_token", value=token, httponly=True, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
                return response
            else:
                return await TemplateResponse.render('login.html', request, session, {"error": "غلط صارف نام یا پاس ورڈ۔", "form_data": data, "errors": {}})
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render('login.html', request, session, {"errors": errors, "form_data": data, "error": None})

    return await TemplateResponse.render('login.html', request, session, {"form": None, "errors": {}, "error": None, "form_data": None})

@router.api_route("/{institution_slug}/login/", methods=["GET", "POST"], name="institution_login")
async def institution_login(request: Request, institution_slug: str, session: Session = Depends(get_session)):
    return await dms_login(request, session)

# --- 4. signup ---
@router.api_route("/signup/", methods=["GET", "POST"], response_class=HTMLResponse, name="dms_signup")
async def signup(request: Request, session: Session = Depends(get_session)):
    from app.schemas.forms import SignupFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = SignupFormSchema(**data)
            success, message, user = UserManager.handle_signup(validated_data.dict(), session)
            if success:
                return RedirectResponse(url="/welcome/", status_code=303)
            return await TemplateResponse.render("signup.html", request, session, {"error": message, "form_data": data})
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render("signup.html", request, session, {"errors": errors, "form_data": data})
        
    return await TemplateResponse.render("signup.html", request, session, {"form": None})

# --- 5. set_default_institution ---
@router.get("/account/set-default/{institution_slug}/", name="set_default_institution")
async def set_default_institution(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    inst = session.exec(select(Institution).where(Institution.slug == institution_slug, Institution.user_id == current_user.id)).first()
    if not inst: raise HTTPException(status_code=404)
    
    # پہلے تمام ڈیفالٹ ختم کریں (Parameterized approach)
    session.execute(update(Institution).where(Institution.user_id == current_user.id).values(is_default=False))
    inst.is_default = True
    session.add(inst)
    session.commit()
    
    return RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)

# --- 6. create_portal_account ---
@router.post("/{institution_slug}/account/create/{person_type}/{person_id}/", name="create_portal_account")
async def create_portal_account(request: Request, institution_slug: str, person_type: str, person_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    
    model_map = {'staff': Staff, 'student': Student, 'parent': Parent}
    model = model_map.get(person_type)
    if not model: raise HTTPException(status_code=400, detail="Invalid person type")
    
    person = session.get(model, person_id)
    if not person or person.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Not found")
        
    if not person.user_id:
        try:
            UserManager.ensure_user(person, prefix=person_type, session=session)
            session.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    return RedirectResponse(url=request.headers.get("referer", f"/{institution_slug}/dashboard"), status_code=303)

# --- 7. auth_google placeholder ---
@router.get("/auth/google/", name="auth_google")
async def auth_google(request: Request, process: str = "login"):
    return RedirectResponse(url="/login/", status_code=303)

