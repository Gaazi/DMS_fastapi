from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_session
from models import Institution, Income, Expense, Fee, Student
from templating import render_template

router = APIRouter(prefix="/dms/{slug}", tags=["finance"])

@router.get("/balance", name="balance")
async def balance_summary(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    total_income = session.query(func.sum(Income.amount)).filter(Income.inst_id == institution.id).scalar() or 0
    total_expense = session.query(func.sum(Expense.amount)).filter(Expense.inst_id == institution.id).scalar() or 0
    
    context = {
        "institution": institution,
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
    }
    return render_template("dms/balance.html", request, context, session)

@router.get("/in", name="income")
async def income_dashboard(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    recent_income = session.query(Income).filter(Income.inst_id == institution.id).order_by(Income.date.desc()).limit(10).all()
    
    context = {
        "institution": institution,
        "recent_income": recent_income,
        "total_income": session.query(func.sum(Income.amount)).filter(Income.inst_id == institution.id).scalar() or 0,
    }
    return render_template("dms/income.html", request, context, session)

@router.get("/out", name="expense")
async def expense_dashboard(request: Request, slug: str, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    if not institution: return {"error": "Institution not found"}
    
    recent_expenses = session.query(Expense).filter(Expense.inst_id == institution.id).order_by(Expense.date.desc()).limit(10).all()
    
    context = {
        "institution": institution,
        "recent_expenses": recent_expenses,
        "total_expenses": session.query(func.sum(Expense.amount)).filter(Expense.inst_id == institution.id).scalar() or 0,
    }
    return render_template("dms/expense.html", request, context, session)

@router.get("/fees/{fee_id}", name="fees")
async def fee_detail(request: Request, slug: str, fee_id: int, session: Session = Depends(get_session)):
    institution = session.query(Institution).filter(Institution.slug == slug).first()
    fee = session.get(Fee, fee_id)
    if not fee: return {"error": "Fee not found"}
    
    context = {
        "institution": institution,
        "fee": fee,
        "student": session.get(Student, fee.student_id),
    }
    return render_template("dms/student_detail.html", request, context, session)
