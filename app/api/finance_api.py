from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
import json

# Internal Imports
from app.db.session import get_session
from app.models import Institution, Donor, Income, Expense, User, Fee, Fee_Payment
from app.logic.auth import get_current_user
from app.logic.finance import FinanceManager
from app.logic.donations import DonationManager
from app.logic.permissions import get_institution_with_access
from app.helper.context import TemplateResponse

router = APIRouter()

from app.logic.payments import Cashier
from decimal import Decimal
from sqlalchemy import func
from app.models import Parent, Fee, Institution, Donor, Income, Expense, User, Fee_Payment

# --- 1. balance (Finance Dashboard) ---
@router.get("/{institution_slug}/balance/", response_class=HTMLResponse, name="balance")
async def balance(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceManager(session, institution, current_user)
    
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    context = fm.balance_dashboard_context(request)
    context.update({
        "request": request, 
        "institution": institution,
        "start_date": start_date,
        "end_date": end_date
    })
    
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'balance-summary-stats':
        return await TemplateResponse.render("dms/partials/balance_summary_partial.html", request, session, context)
    return await TemplateResponse.render("dms/balance.html", request, session, context)

# --- 2. fee payment ---
@router.post("/{institution_slug}/fees/{fee_id}/pay/", name="pay_installment")
async def pay_installment(request: Request, institution_slug: str, fee_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    form_data = await request.form()
    data = dict(form_data)
    
    amount = float(data.get('amount', 0))
    method = data.get('method', 'Cash')
    student_id = int(data.get('student_id')) if data.get('student_id') else None
    use_wallet = data.get('use_wallet') == 'on'
    
    admission_id = int(data.get('admission_id')) if data.get('admission_id') else None
    
    cashier = Cashier(session, institution, current_user)
    try:
        result = cashier.collect_fee(
            fee_id=fee_id if fee_id != 0 else None,
            student_id=student_id,
            admission_id=admission_id,
            amount=amount,
            method=method,
            use_wallet=use_wallet
        )
        
        from app.helper.helper import number_to_words
        from app.logic.institution import InstitutionManager
        context = {
            "result": result["result"],
            "student": result["student"],
            "amount": result["amount"],
            "currency_label": InstitutionManager.get_currency_label(institution),
            "amount_words": number_to_words(result["amount"]),
            "is_advance": fee_id == 0,
            "message": "ادائیگی کامیابی سے مکمل ہو گئی۔",
            "request": request,
            "institution": institution
        }
        
        response = await TemplateResponse.render('dms/partials/receipt_fee.html', request, session, context)
        response.headers['HX-Trigger'] = json.dumps({"refreshFeeTable": None, "closeModal": None, "updateBalance": None})
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

# --- 3. bulk fee collect (Waterfall) ---
@router.post("/{institution_slug}/fees/collect/", name="collect_fee_bulk")
async def collect_fee_bulk(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    cashier = Cashier(session, institution, current_user)
    form_data = await request.form()
    data = dict(form_data)
    
    cashier.collect_fee(
        student_id=int(data.get('student_id')) if data.get('student_id') else None,
        amount=float(data.get('amount', 0)),
        method=data.get('method', 'Cash'),
        use_wallet=data.get('use_wallet') == 'on'
    )
    
    response = RedirectResponse(url=request.headers.get("Referer", f"/{institution_slug}/students/"), status_code=303)
    response.headers['HX-Trigger'] = json.dumps({"updateBalance": None, "refreshStudent": None})
    return response

# --- 4. batch_generate_fees ---
@router.api_route("/{institution_slug}/fees/generate-batch/", methods=["GET", "POST"], name="batch_generate_fees")
async def batch_generate_fees(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    if request.method == "POST":
        form_data = await request.form()
        fm = FinanceManager(session, institution, current_user)
        fm.auto_generate_fees(year=int(form_data.get('year')), month=int(form_data.get('month')))
        return RedirectResponse(url=request.url_for("balance", institution_slug=institution_slug), status_code=303)
    return await TemplateResponse.render("dms/batch_fee_form.html", request, session, {"institution": institution})

# --- 5. record income/donation ---
@router.api_route("/{institution_slug}/in/create/", methods=["GET", "POST"], name="income_create")
async def record_income(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    from app.schemas.forms import IncomeFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        
        try:
            # Validate input data
            validated_data = IncomeFormSchema(**data)
            
            fm = FinanceManager(session, institution, current_user)
            income = fm.record_income(
                source=validated_data.source,
                amount=validated_data.amount,
                donor_id=validated_data.donor_id,
                description=validated_data.description
            )
            
            if request.headers.get('HX-Request'):
                response = HTMLResponse(content="<div class='p-3 bg-emerald-500/10 text-emerald-400 font-bold rounded-xl animate-fade-in'>آمدنی درج کر لی گئی۔ (Success)</div>")
                response.headers['HX-Trigger'] = json.dumps({"incomeCreated": None, "updateBalance": None})
                return response
            return RedirectResponse(url=request.url_for("income", institution_slug=institution_slug), status_code=303)
            
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            donors = session.exec(select(Donor).where(Donor.inst_id == institution.id)).all()
            context = {
                "institution": institution, 
                "donors": donors, 
                "errors": errors, 
                "form_data": data
            }
            # Re-render partial if HTMX
            if request.headers.get('HX-Request'):
                return await TemplateResponse.render("dms/partials/income_form_partial.html", request, session, context)
            return await TemplateResponse.render("dms/income_form.html", request, session, context)
    
    donors = session.exec(select(Donor).where(Donor.inst_id == institution.id)).all()
    context = {"institution": institution, "donors": donors}
    return await TemplateResponse.render("dms/income_form.html", request, session, context)

# --- 6. record expense ---
@router.api_route("/{institution_slug}/out/create/", methods=["GET", "POST"], name="expense_out_create")
async def record_expense(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    from app.schemas.forms import ExpenseFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        
        try:
            validated_data = ExpenseFormSchema(**data)
            
            fm = FinanceManager(session, institution, current_user)
            fm.record_expense(
                category=validated_data.category,
                amount=validated_data.amount,
                description=validated_data.description,
                date=validated_data.date
            )
            
            if request.headers.get('HX-Request'):
                response = HTMLResponse(content="<div class='p-3 bg-emerald-500/10 text-emerald-400 font-bold rounded-xl animate-fade-in'>اخراجات درج کر لیے گئے۔ (Success)</div>")
                response.headers['HX-Trigger'] = json.dumps({"expenseCreated": None, "updateBalance": None})
                return response
            return RedirectResponse(url=request.url_for("expense", institution_slug=institution_slug), status_code=303)
            
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            context = {
                "institution": institution, 
                "errors": errors, 
                "form_data": data
            }
            if request.headers.get('HX-Request'):
                return await TemplateResponse.render("dms/partials/expense_form_partial.html", request, session, context)
            return await TemplateResponse.render("dms/expense_form.html", request, session, context)
            
    return await TemplateResponse.render("dms/expense_form.html", request, session, {"institution": institution})

# --- 7. donor management ---
@router.api_route("/{institution_slug}/donor/", methods=["GET", "POST"], name="donor")
async def donor_list(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    dm = DonationManager(session, current_user, institution=institution)
    
    from app.schemas.forms import DonorFormSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        try:
            validated_data = DonorFormSchema(**data)
            dm.get_or_create_donor(validated_data.dict())
            return RedirectResponse(url=request.url.path, status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            donors = session.exec(select(Donor).where(Donor.inst_id == institution.id).order_by(Donor.name)).all()
            return await TemplateResponse.render("dms/donor.html", request, session, {
                "institution": institution, "donors": donors, "errors": errors, "stats": dm.get_detailed_summary(), "form_data": data
            })

    donors = session.exec(select(Donor).where(Donor.inst_id == institution.id).order_by(Donor.name)).all()
    context = {
        "request": request,
        "institution": institution,
        "donors": donors,
        "stats": dm.get_detailed_summary()
    }
    return await TemplateResponse.render("dms/donor.html", request, session, context)

# --- 7.1 donor_detail ---
@router.get("/{institution_slug}/donor/{donor_id}/", response_class=HTMLResponse, name="donor_detail")
async def donor_detail(request: Request, institution_slug: str, donor_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    donor = session.get(Donor, donor_id)
    if not donor or donor.inst_id != institution.id:
        raise HTTPException(status_code=404, detail="Donor not found")
        
    dm = DonationManager(session, current_user, institution=institution)
    context = dm.get_donor_analytics(donor)
    context.update({"request": request, "institution": institution})
    return await TemplateResponse.render("dms/donor_detail.html", request, session, context)

# --- 1. fees ---
@router.get("/{institution_slug}/fees/{fee_id}/", response_class=HTMLResponse, name="fees")
async def fees(request: Request, institution_slug: str, fee_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceManager(session, institution, current_user)
    context = fm.fee_detail(fee_id)
    context.update({"request": request, "institution": institution})
    return await TemplateResponse.render('dms/student_detail.html', request, session, context)

# --- 2. pay_installment ---
# This route is replaced by pay_fee_route and collect_fee_bulk
# @router.post("/{institution_slug}/fees/{fee_id}/pay/")
# async def pay_installment(
#     request: Request, institution_slug: str, fee_id: int,
#     session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
# ):
#     institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
#     fm = FinanceManager(current_user, session=session, institution=institution)
#     form_data = await request.form()
    
#     result = fm.pay(
#         fee_id=fee_id if fee_id != 0 else None,
#         student_id=form_data.get('student_id'),
#         amount=form_data.get('amount', 0),
#         method=form_data.get('method', 'Cash'),
#         use_wallet=form_data.get('use_wallet') == 'on'
#     )
    
#     if result['status'] == 'success':
#         response = await TemplateResponse.render('dms/partials/receipt_fee.html', request, session, result)
#         response.headers['HX-Trigger'] = json.dumps({"updateBalance": None, "refreshFeeTable": None, "closeModal": None})
#         return response
            
#     raise HTTPException(status_code=400, detail="ادائیگی مکمل نہیں ہوسکی۔")

# --- 2.1 batch_generate_fees ---
# This route is now at position 4.

# --- 3. balance ---
# This route is now at position 1.

# --- 4. donation (آمدنی ڈیش بورڈ) ---
@router.get("/{institution_slug}/in/", response_class=HTMLResponse, name="income")
async def donation(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceManager(session, institution, current_user)
    context = fm.income_dashboard_context(request) # Assuming this method exists and returns the necessary context
    context.update({"request": request, "institution": institution})
    
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'income-dashboard-summary':
        return await TemplateResponse.render("dms/partials/income_dashboard_summary_partial.html", request, session, context)
    return await TemplateResponse.render("dms/income.html", request, session, context)

# --- 5. income_create ---
# This route is now at position 5 (record_income).

# --- 6. income_detail ---
@router.get("/{institution_slug}/in/{income_id}/", response_class=HTMLResponse, name="income_detail")
async def income_detail(request: Request, institution_slug: str, income_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    income = session.get(Income, income_id)
    return await TemplateResponse.render('dms/income_detail.html', request, session, {'institution': institution, 'income': income})

# --- 7. expense ---
@router.get("/{institution_slug}/out/", response_class=HTMLResponse, name="expense")
async def expense(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceManager(session, institution, current_user)
    context = fm.expenses_dashboard_context(request) # Assuming this method exists and returns the necessary context
    context.update({"request": request, "institution": institution})
    
    if request.headers.get('HX-Request'):
        return await TemplateResponse.render("dms/partials/expense_table_partial.html", request, session, context)
    return await TemplateResponse.render("dms/expense.html", request, session, context)

# --- 8. donation_in_overview ---
@router.get("/{institution_slug}/in/list/", response_class=HTMLResponse, name="donation_in_overview")
async def donation_in_overview(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    dm = DonationManager(session, current_user, institution=institution)
    context = dm.get_donation_list_context(page=request.query_params.get("page"))
    context.update({"request": request, "institution": institution})
    
    if request.headers.get('HX-Request'):
        return await TemplateResponse.render("dms/partials/income_table_partial.html", request, session, context)
    return await TemplateResponse.render("dms/income_list.html", request, session, context)

# --- 9. donor ---
# This route is now at position 7 (donor_list).

# --- 10. donor_create_quick ---
@router.post("/{institution_slug}/donor/quick-save/")
async def donor_create_quick(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    dm = DonationManager(session, current_user, institution=institution)
    form_data = await request.form()
    success, message, donor_obj = dm.get_or_create_donor(dict(form_data))
    if success:
        response = HTMLResponse(content=f"<div class='p-3 bg-emerald-500/10 text-emerald-400'>{message}</div>")
        response.headers['HX-Trigger'] = json.dumps({"donor-saved": {"id": donor_obj.id, "name": donor_obj.name}, "incomeCreated": None})
        return response
    raise HTTPException(status_code=400, detail=message)

# --- 10.1 Donor Full CRUD ---
@router.api_route("/{institution_slug}/donor/add/", methods=["GET", "POST"], name="donor_create")
@router.api_route("/{institution_slug}/donor/{donor_id}/edit/", methods=["GET", "POST"], name="donor_edit")
async def donor_create_edit(request: Request, institution_slug: str, donor_id: Optional[int] = None, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    dm = DonationManager(session, current_user, institution=institution)
    if request.method == "POST":
        form_data = await request.form()
        dm.update_donor(donor_id, dict(form_data)) # Assuming update_donor method exists
        return RedirectResponse(url=f"/{institution_slug}/donor/", status_code=303)
    editing_donor = session.get(Donor, donor_id) if donor_id else None
    return await TemplateResponse.render("dms/donor_form.html", request, session, {"institution": institution, "editing_donor": editing_donor})

@router.post("/{institution_slug}/donor/{donor_id}/delete/", name="donor_delete")
async def donor_delete(institution_slug: str, donor_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='admin')
    donor_obj = session.get(Donor, donor_id)
    if donor_obj:
        session.delete(donor_obj)
        session.commit()
    return RedirectResponse(url=f"/{institution_slug}/donor/", status_code=303)

# --- 11. public_donation & support ---
@router.api_route("/{institution_slug}/support/", methods=["GET", "POST"], response_class=HTMLResponse, name="public_support")
async def public_support(request: Request, institution_slug: str, session: Session = Depends(get_session)):
    return await public_donation(request, institution_slug, session)

@router.api_route("/{institution_slug}/donate/", methods=["GET", "POST"], response_class=HTMLResponse, name="public_donation")
async def public_donation(request: Request, institution_slug: str, session: Session = Depends(get_session)):
    institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    if not institution: raise HTTPException(status_code=404)
    
    from app.schemas.forms import PublicDonationSchema
    from pydantic import ValidationError
    from app.logic.finance_donation import DonationManager

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        
        try:
            validated = PublicDonationSchema(**data)
            dm = DonationManager(session, None, institution=institution)
            success, message, _ = dm.handle_public_donation(validated.dict())
            if success:
                return await TemplateResponse.render("dms/public_success.html", request, session, {"institution": institution})
            else:
                return await TemplateResponse.render("dms/public_donation.html", request, session, {
                    "institution": institution, "error_msg": message, "form_data": data
                })
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            return await TemplateResponse.render("dms/public_donation.html", request, session, {
                "institution": institution, "errors": errors, "form_data": data
            })

    return await TemplateResponse.render("dms/public_donation.html", request, session, {"institution": institution})

@router.api_route("/{institution_slug}/fees/family/", methods=["GET", "POST"], response_class=HTMLResponse, name="family_fee_collection")
async def family_fee_collection(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    
    # Handle both query params and form data for family_id
    form_data_raw = await request.form() if request.method == "POST" else {}
    family_id = request.query_params.get('family_id') or form_data_raw.get('family_id')
    
    parent = None
    results = None
    
    if request.method == "POST":
        data = dict(form_data_raw)
        action = data.get('action')
        
        if action == "pay":
            f_id = data.get('family_id')
            amount = float(data.get('amount', 0))
            method = data.get('method', 'Cash')
            
            cashier = Cashier(session, institution, current_user)
            results = cashier.collect_family_fee(family_id=f_id, amount=amount, method=method)
            
            return await TemplateResponse.render("dms/receipt_family.html", request, session, {
                "institution": institution,
                "results": results,
                "total_paid": amount
            })

    if family_id:
        parent = session.exec(select(Parent).where(Parent.family_id == family_id, Parent.inst_id == institution.id)).first()
        if parent:
            # Aggregate dues for display
            total_family_dues = 0
            for student in parent.students:
                dues = session.exec(select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
                    Fee.student_id == student.id, Fee.status != 'Paid'
                )).one() or 0
                student.total_dues = float(dues)
                total_family_dues += student.total_dues
            parent.total_family_dues = total_family_dues

    context = {
        "request": request,
        "institution": institution,
        "parent": parent,
        "family_id": family_id
    }
    return await TemplateResponse.render("dms/family_payment.html", request, session, context)

@router.get("/{institution_slug}/reports/family-dues/", response_class=HTMLResponse, name="family_financial_report")
async def family_financial_report(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceManager(session, institution, current_user)
    
    report_data = fm.get_family_financial_report()
    
    context = {
        "request": request,
        "institution": institution,
        "report_data": report_data
    }
    return await TemplateResponse.render("dms/family_report.html", request, session, context)
