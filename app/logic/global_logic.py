from typing import List, Optional, Any, Dict
from decimal import Decimal
from sqlmodel import Session, select, func
from fastapi import HTTPException
from app.models import Institution, Income, Expense, Student, Staff, Course
from app.logic.auth import UserLogic

# Constants
try:
    from app.constants import TYPE_LABELS, VALID_TYPES
except ImportError:
    TYPE_LABELS = {
        'school': {'title': 'School', 'icon': 'school'},
        'college': {'title': 'College', 'icon': 'account_balance'},
        'madrasa': {'title': 'Madrasa', 'icon': 'mosque'},
        'academy': {'title': 'Academy', 'icon': 'psychology'},
        'other': {'title': 'Other', 'icon': 'business'}
    }
    VALID_TYPES = list(TYPE_LABELS.keys())

class GlobalLogic:
    """Central manager for global reporting and multi-institution logic (FastAPI/SQLModel Version)"""

    def __init__(self, user, session: Session):
        self.user = user
        self.session = session
        self._check_access()

    def _check_access(self):
        """Ensure only authenticated users can access global logic."""
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required.")

    def get_global_overview(self):
        """تمام اقسام کے اداروں کا مجموعی مالیاتی اور انتظامی خلاصہ تیار کرنا۔"""
        from app.logic.auth import UserLogic
        user_institutions = UserLogic.get_user_institutions(self.user, self.session)
        institution_ids = [inst.id for inst in user_institutions]
        
        summary = {
            key: {
                "meta": TYPE_LABELS[key],
                "institution_count": 0,
                "total_income": Decimal('0.00'),
                "total_expense": Decimal('0.00'),
                "balance": Decimal('0.00'),
                "student_count": 0,
                "staff_count": 0,
                "course_count": 0,
            }
            for key in VALID_TYPES
        }

        if not institution_ids:
            return {"type_summary": summary, "totals": {}}

        # 1. اداروں کی تعداد
        stmt_inst = select(Institution.type, func.count(Institution.id)).where(Institution.id.in_(institution_ids)).group_by(Institution.type)
        for inst_type, count in self.session.exec(stmt_inst).all():
            if inst_type in summary: summary[inst_type]["institution_count"] = count

        # 2. آمدنی ایگریگیشن
        stmt_inc = select(Institution.type, func.sum(Income.amount)).join(Income, Income.inst_id == Institution.id).where(Institution.id.in_(institution_ids)).group_by(Institution.type)
        for inst_type, total in self.session.exec(stmt_inc).all():
            if inst_type in summary: summary[inst_type]["total_income"] = total or Decimal('0.00')

        # 3. اخراجات ایگریگیشن
        stmt_exp = select(Institution.type, func.sum(Expense.amount)).join(Expense, Expense.inst_id == Institution.id).where(Institution.id.in_(institution_ids)).group_by(Institution.type)
        for inst_type, total in self.session.exec(stmt_exp).all():
            if inst_type in summary: summary[inst_type]["total_expense"] = total or Decimal('0.00')

        # 4. طلبہ، اسٹاف اور کورسز
        for model, field in [(Student, "student_count"), (Staff, "staff_count"), (Course, "course_count")]:
             stmt = select(Institution.type, func.count(model.id)).join(model, model.inst_id == Institution.id).where(Institution.id.in_(institution_ids)).group_by(Institution.type)
             for inst_type, count in self.session.exec(stmt).all():
                 if inst_type in summary: summary[inst_type][field] = count

        # Final totals
        total_metrics = {
            "institutions": sum(d["institution_count"] for d in summary.values()),
            "income": sum(d["total_income"] for d in summary.values()),
            "expense": sum(d["total_expense"] for d in summary.values()),
            "students": sum(d["student_count"] for d in summary.values()),
            "staff": sum(d["staff_count"] for d in summary.values()),
            "courses": sum(d["course_count"] for d in summary.values()),
        }
        total_metrics["balance"] = total_metrics["income"] - total_metrics["expense"]

        return {
            "type_summary": summary,
            "totals": total_metrics,
            "type_choices": TYPE_LABELS,
            "institutions": user_institutions
        }


    def get_institutions_by_type(self, inst_type: str):
        """کسی مخصوص قسم کے تمام متعلقہ اداروں کی فہرست حاصل کرنا۔"""
        user_institutions = UserLogic.get_user_institutions(self.user, self.session)
        institution_ids = [inst.id for inst in user_institutions]
        
        stmt = select(Institution).where(
            Institution.id.in_(institution_ids),
            Institution.type == inst_type
        ).order_by(Institution.name)
        
        return self.session.exec(stmt).all()

    def get_type_list_context(self, inst_type: str):
        """مخصوص قسم کے اداروں والے صفحے کے لیے تمام ضروری ڈیٹا اکٹھا کرنا۔"""
        if inst_type not in VALID_TYPES:
            raise HTTPException(status_code=404, detail="Unknown institution type.")

        institutions = self.get_institutions_by_type(inst_type)
        
        # صرف وہ "Types" دکھائیں جن میں یوزر کا کم از کم ایک ادارہ موجود ہے
        all_user_inst = UserLogic.get_user_institutions(self.user, self.session)
        user_inst_types = set(inst.type for inst in all_user_inst)
        
        scoped_type_choices = {
            k: v for k, v in TYPE_LABELS.items() 
            if k in user_inst_types
        }
            
        return {
            "institutions": institutions,
            "institution_type": inst_type,
            "type_meta": TYPE_LABELS[inst_type],
            "type_choices": scoped_type_choices
        }

