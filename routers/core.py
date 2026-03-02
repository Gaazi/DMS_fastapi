from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_session
from models import Institution, Student, Staff, Income, Expense
from templating import render_template
from pathlib import Path

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent

@router.get("/manifest.json")
async def manifest():
    from fastapi.responses import FileResponse
    manifest_path = BASE_DIR / "static" / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path)
    return {"error": "manifest.json not found"}

@router.get("/overview", name="institution_overview")
async def institution_overview(request: Request, session: Session = Depends(get_session)):
    stats = {
        "total_institutions": session.query(Institution).count(),
        "total_students": session.query(Student).count(),
        "total_staff": session.query(Staff).count(),
        "total_income": session.query(func.sum(Income.amount)).scalar() or 0,
        "total_expense": session.query(func.sum(Expense.amount)).scalar() or 0,
    }
    context = {
        "stats": stats,
        "institutions": session.query(Institution).all(),
    }
    return render_template("dms/institution_overview.html", request, context, session)

@router.get("/", name="home")
async def home(request: Request, session: Session = Depends(get_session)):
    total_income = session.query(func.sum(Income.amount)).scalar() or 0
    total_expense = session.query(func.sum(Expense.amount)).scalar() or 0
    
    context = {
        "total_institutions": session.query(Institution).count(),
        "total_income": total_income,
        "total_expense": total_expense,
        "total_balance": total_income - total_expense,
    }
    return render_template("dms/dms.html", request, context, session)
