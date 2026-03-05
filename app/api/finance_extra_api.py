from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, func
from typing import Optional
from datetime import datetime

# Internal Imports
from app.core.database import get_session
from app.models import User, Institution, Income, Expense
from app.logic.auth import get_current_user
from app.logic.permissions import get_institution_with_access

router = APIRouter()

from app.utils.context import TemplateResponse
from app.logic.finance import FinanceLogic

# --- 1. income_edit ---
@router.api_route("/{institution_slug}/income/edit/{income_id}", methods=["GET", "POST"], name="income_edit")
async def income_edit(request: Request, institution_slug: str, income_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """انکم ریکارڈ میں ترمیم۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceLogic(session, institution, current_user)
    from app.schemas.forms import IncomeFormSchema
    from pydantic import ValidationError
    
    income = session.exec(select(Income).where(Income.id == income_id, Income.inst_id == institution.id)).first()
    if not income: raise HTTPException(status_code=404)
    
    errors = None
    form_data = None

    if request.method == "POST":
        raw_form = await request.form()
        form_data = dict(raw_form)
        try:
            validated = IncomeFormSchema(**form_data)
            fm.update_income(income_id, validated.dict())
            return RedirectResponse(url=f"/{institution_slug}/finance", status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
    
    return await TemplateResponse.render("dms/income_form.html", request, session, {
        "institution": institution,
        "editing": True,
        "income": income,
        "errors": errors,
        "form_data": form_data,
        "title": f"Edit Income #{income.receipt_number}"
    })

# --- 2. expense_edit ---
@router.api_route("/{institution_slug}/expense/edit/{expense_id}", methods=["GET", "POST"], name="expense_edit")
async def expense_edit(request: Request, institution_slug: str, expense_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """اخراجات ریکارڈ میں ترمیم۔"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    fm = FinanceLogic(session, institution, current_user)
    from app.schemas.forms import ExpenseFormSchema
    from pydantic import ValidationError
    
    expense = session.exec(select(Expense).where(Expense.id == expense_id, Expense.inst_id == institution.id)).first()
    if not expense: raise HTTPException(status_code=404)
    
    errors = None
    form_data = None

    if request.method == "POST":
        raw_form = await request.form()
        form_data = dict(raw_form)
        try:
            validated = ExpenseFormSchema(**form_data)
            fm.update_expense(expense_id, validated.dict())
            return RedirectResponse(url=f"/{institution_slug}/finance", status_code=303)
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
    
    return await TemplateResponse.render("dms/expense_form.html", request, session, {
        "institution": institution,
        "editing": True,
        "expense": expense,
        "errors": errors,
        "form_data": form_data,
        "title": f"Edit Expense #{expense.receipt_number}"
    })

# --- 3. transaction_report ---
@router.get("/{institution_slug}/reports/transactions", response_class=HTMLResponse, name="transaction_report")
async def transaction_report(request: Request, institution_slug: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Transaction Report (PDF/HTML Preview)"""
    institution, access = get_institution_with_access(institution_slug, session, current_user, access_type='finance')
    
    expenses = session.exec(select(Expense).where(Expense.inst_id == institution.id).order_by(Expense.date.desc())).all()
    total = session.exec(select(func.sum(Expense.amount)).where(Expense.inst_id == institution.id)).one() or 0

    return await TemplateResponse.render("dms/reports/transaction_report.html", request, session, {
        "institution": institution,
        "expenses": expenses,
        "total": total,
        "today_date": datetime.now().date()
    })

