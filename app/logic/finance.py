from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime, timedelta
from decimal import Decimal
import json

# Models
from app.models import (
    Institution, Student, Admission, Fee, Fee_Payment, 
    Income, Expense, WalletTransaction, User, Donor
)
from app.logic.audit import AuditManager

class FinanceManager:
    """ادارے کا مکمل مالیاتی نظام: فیسیں، آمدن، اخراجات اور اینالیٹکس (FastAPI Version)۔"""
    
    def __init__(self, session: Session, institution: Institution, user: Optional[User] = None, student: Optional[Student] = None):
        self.user = user
        self.session = session
        self.institution = institution
        self.student = student

    def student_fee_history(self, student_id: Optional[int] = None) -> List[Fee]:
        """طالب علم کی فیسوں کی مکمل تاریخ بشمول ادائیگیوں کے۔"""
        sid = student_id or (self.student.id if self.student else None)
        if not sid: return []
        
        statement = select(Fee).where(Fee.student_id == sid).order_by(desc(Fee.month), desc(Fee.id))
        return self.session.exec(statement).all()

    def get_student_fee_totals(self, student_id: Optional[int] = None) -> dict:
        """طالب علم کی مجموعی فیس، ادا شدہ رقم اور بقایا جات کا حساب۔"""
        sid = student_id or (self.student.id if self.student else None)
        if not sid: return {'total_due': 0, 'total_paid': 0, 'balance': 0}

        fees = self.student_fee_history(sid)
        total_due = sum((f.amount_due + (f.late_fee or 0) - (f.discount or 0)) for f in fees if f.status != 'Cancelled')
        total_paid = sum(f.amount_paid for f in fees)
        balance = sum((f.amount_due + (f.late_fee or 0) - (f.discount or 0) - f.amount_paid) for f in fees if f.status in ['Pending', 'Partial'])
        return {
            'total_due': total_due,
            'total_paid': total_paid,
            'balance': balance
        }

    def currency(self):
        return str(getattr(self.institution, 'currency_label', 'Rs'))

    def generate_initial_fees_for_admission(self, admission: Admission):
        """داخلہ ہوتے ہی ایڈمیشن اور پہلی فیس کا ریکارڈ بنانا۔"""
        # 1. ایڈمیشن فیس
        base_date = admission.admission_date or dt_date.today()
        if admission.agreed_admission_fee and admission.agreed_admission_fee > 0:
            adm_fee = Fee(
                inst_id=admission.inst_id,
                student_id=admission.student_id,
                admission_id=admission.id,
                course_id=admission.course_id,
                fee_type='admission',
                amount_due=admission.agreed_admission_fee,
                title="Admission Fee",
                due_date=base_date,
                month=base_date.replace(day=1),
                status='Pending'
            )
            self.session.add(adm_fee)
        
        # 2. پہلی ماہانہ فیس
        if admission.agreed_course_fee and admission.agreed_course_fee > 0:
            first_fee = Fee(
                inst_id=admission.inst_id,
                student_id=admission.student_id,
                admission_id=admission.id,
                course_id=admission.course_id,
                fee_type='monthly',
                amount_due=admission.agreed_course_fee,
                title=f"Monthly Fee ({base_date.strftime('%B')})",
                due_date=base_date,
                month=base_date.replace(day=1),
                status='Pending'
            )
            self.session.add(first_fee)
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'initial_fees', 'Admission', admission.id, f"Initial fees for admission #{admission.id}", {})
        self.session.commit()

    def auto_generate_fees(self, year=None, month=None):
        """ہر مہینے خودکار طور پر فیسیں تیار کرنا۔"""
        self._check_access()
        now = dt_date.today()
        target_month = now.replace(year=year or now.year, month=month or now.month, day=1)
        
        # target_month logic remains
        count = 0

        admissions = self.session.exec(select(Admission).where(Admission.status == 'active')).all()
        
        count = 0
        for ad in admissions:
            # طالب علم کا انسٹی ٹیوشن چیک کریں
            student = self.session.get(Student, ad.student_id)
            if not student or student.inst_id != self.institution.id: continue

            # Check if fee already exists for THIS student admission in this month
            exists_stmt = select(func.count(Fee.id)).where(
                Fee.student_id == ad.student_id,
                Fee.admission_id == ad.id,
                Fee.month == target_month,
                Fee.fee_type == 'monthly'
            )
            if self.session.exec(exists_stmt).one() > 0: continue

            fee = Fee(
                inst_id=self.institution.id,
                student_id=ad.student_id,
                admission_id=ad.id,
                course_id=ad.course_id,
                fee_type='monthly',
                amount_due=ad.agreed_course_fee or 0,
                title=f"Monthly Fee ({target_month.strftime('%B %Y')})",
                due_date=target_month.replace(day=10),
                month=target_month,
                status='Pending'
            )
            self.session.add(fee)
            count += 1
            
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'auto_generate', 'Fee', 0, f"Generated {count} monthly fees", {'month': target_month.isoformat()})
        self.session.commit()
        return count

    def record_expense(self, category: str, amount: Decimal, description: str, date: Optional[dt_date] = None):
        """اخراجات کا اندراج کرنا۔"""
        expense = Expense(
            inst_id=self.institution.id,
            category=category,
            amount=amount,
            description=description,
            date=date or dt_date.today()
        )
        self.session.add(expense)
        self.session.flush()
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'expense', 'Expense', expense.id, description, {'amount': float(amount)})
        self.session.commit()
        self.session.refresh(expense)
        return expense

    def record_income(self, source: str, amount: Decimal, description: str, date: Optional[dt_date] = None):
        """آمدنی کا اندراج۔"""
        income = Income(
            inst_id=self.institution.id,
            source=source,
            amount=amount,
            description=description,
            date=date or dt_date.today()
        )
        self.session.add(income)
        self.session.flush()
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'income', 'Income', income.id, description, {'amount': float(amount)})
        self.session.commit()
        self.session.refresh(income)
        return income

    def update_income(self, income_id: int, data: dict):
        """آمدنی کے ریکارڈ میں تبدیلی۔"""
        self._check_access()
        income = self.session.get(Income, income_id)
        if not income or income.inst_id != self.institution.id:
            raise HTTPException(status_code=404, detail="Income record not found.")
        
        old_data = {k: getattr(income, k) for k in data.keys() if hasattr(income, k)}
        for k, v in data.items():
            if hasattr(income, k): setattr(income, k, v)
        
        self.session.add(income)
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'update', 'Income', income.id, income.source, {'old': old_data, 'new': data})
        self.session.commit()
        return True, "Income updated.", income

    def update_expense(self, expense_id: int, data: dict):
        """اخراجات کے ریکارڈ میں تبدیلی۔"""
        self._check_access()
        expense = self.session.get(Expense, expense_id)
        if not expense or expense.inst_id != self.institution.id:
            raise HTTPException(status_code=404, detail="Expense record not found.")
        
        old_data = {k: getattr(expense, k) for k in data.keys() if hasattr(expense, k)}
        for k, v in data.items():
            if hasattr(expense, k): setattr(expense, k, v)
            
        self.session.add(expense)
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'update', 'Expense', expense.id, expense.category, {'old': old_data, 'new': data})
        self.session.commit()
        return True, "Expense updated.", expense

    def institution_summary(self, start_date=None, end_date=None):
        """آمدن، اخراجات اور بیلنس کا خلاصہ۔"""
        inc_stmt = select(func.sum(Income.amount)).where(Income.inst_id == self.institution.id)
        exp_stmt = select(func.sum(Expense.amount)).where(Expense.inst_id == self.institution.id)
        
        if start_date and end_date:
            # Handle string dates if necessary
            if isinstance(start_date, str): start_date = dt_date.fromisoformat(start_date)
            if isinstance(end_date, str): end_date = dt_date.fromisoformat(end_date)
            inc_stmt = inc_stmt.where(Income.date >= start_date, Income.date <= end_date)
            exp_stmt = exp_stmt.where(Expense.date >= start_date, Expense.date <= end_date)
            
        total_in = self.session.exec(inc_stmt).one() or Decimal('0.00')
        total_out = self.session.exec(exp_stmt).one() or Decimal('0.00')
        
        return {
            'total_amount': total_in, 
            'total_expenses': total_out, 
            'balance': total_in - total_out,
            'revenue': {'total': total_in}
        }

    def income_dashboard_context(self, request: Any):
        stmt = select(Income).where(Income.inst_id == self.institution.id).order_by(desc(Income.date), desc(Income.id))
        latest = self.session.exec(stmt.limit(10)).all()
        total_count = self.session.exec(select(func.count(Income.id)).where(Income.inst_id == self.institution.id)).one()
        summary = self.institution_summary()
        
        # Mocking Django-style page_obj for template compatibility
        page_obj = {
            'has_other_pages': False,
            'number': 1,
            'paginator': {'num_pages': 1, 'count': total_count}
        }
        
        summary_extended = self.get_institution_financial_summary()
        return {
            "incomes": latest, # Template expects 'incomes'
            "latest_income": latest,
            "total_donations": summary['total_amount'],
            "total_amount": summary['total_amount'], # Used in logic
            "total_expenses": summary['total_expenses'],
            "latest_donation_amount": latest[0].amount if latest else 0,
            "balance": summary['balance'],
            "total_pending": summary_extended['total_pending'],
            "page_obj": page_obj,
            "top_donors": [], # Fallback for now
            "monthly_totals": [] # Fallback for now
        }

    def expenses_dashboard_context(self, request: Any):
        stmt = select(Expense).where(Expense.inst_id == self.institution.id).order_by(desc(Expense.date), desc(Expense.id))
        latest = self.session.exec(stmt.limit(10)).all()
        total_count = self.session.exec(select(func.count(Expense.id)).where(Expense.inst_id == self.institution.id)).one()
        summary = self.institution_summary()
        
        page_obj = {
            'has_other_pages': False,
            'number': 1,
            'paginator': {'num_pages': 1, 'count': total_count}
        }
        
        summary_extended = self.get_institution_financial_summary()
        return {
            "expenses": latest,
            "latest_expenses": latest,
            "total_amount": summary['total_amount'],
            "total_expenses": summary['total_expenses'],
            "latest_expense_amount": latest[0].amount if latest else 0,
            "balance": summary['balance'],
            "total_pending": summary_extended['total_pending'],
            "page_obj": page_obj,
            "expenses_count": total_count
        }

    def balance_dashboard_context(self, request: Any):
        summary = self.institution_summary()
        incomes = self.session.exec(select(Income).where(Income.inst_id == self.institution.id).order_by(desc(Income.date), desc(Income.id)).limit(20)).all()
        expenses = self.session.exec(select(Expense).where(Expense.inst_id == self.institution.id).order_by(desc(Expense.date), desc(Expense.id)).limit(20)).all()
        
        txs = []
        for i in incomes:
            txs.append({
                'id': i.id, 'amount': i.amount, 'transaction_type': 'income', 
                'date': i.date, 'source': i.source, 'description': i.description or "",
                'running_balance': summary['balance']
            })
        for e in expenses:
            txs.append({
                'id': e.id, 'amount': e.amount, 'transaction_type': 'expense', 
                'date': e.date, 'source': e.category, 'description': e.description or "",
                'running_balance': summary['balance']
            })
        
        txs.sort(key=lambda x: (x['date'], x['id']), reverse=True)
        
        page_obj = {
            'has_other_pages': False,
            'number': 1,
            'paginator': {'num_pages': 1, 'count': len(txs)}
        }
        
        summary_extended = self.get_institution_financial_summary()
        
        return {
            "recent_transactions": txs[:15],
            "total_amount": summary['total_amount'],
            "total_expenses": summary['total_expenses'],
            "balance": summary['balance'],
            "page_obj": page_obj,
            "summary": summary,
            "course_stats": summary_extended['course_stats'],
            "total_pending": summary_extended['total_pending']
        }

    def pay_fee(self, fee_id: int, amount: Decimal, method: str = "Cash"):
        """فیس کی ادائیگی وصول کرنا۔"""
        self._check_access()
        fee = self.session.get(Fee, fee_id)
        if not fee: raise HTTPException(status_code=404, detail="Fee not found.")
        
        from app.logic.payments import generate_transaction_id
        receipt_no = generate_transaction_id(self.institution, "REC", fee.student_id)

        payment = Fee_Payment(
            inst_id=self.institution.id,
            student_id=fee.student_id,
            fee_id=fee.id,
            amount=amount,
            payment_method=method,
            receipt_number=receipt_no
        )
        self.session.add(payment)
        self.session.flush()
        
        fee.amount_paid += amount
        if fee.amount_paid >= (fee.amount_due + fee.late_fee - fee.discount):
            fee.status = 'Paid'
        else:
            fee.status = 'Partial'
            
        self.session.add(fee)
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'pay_fee', 'Fee', fee.id, f"Payment for {fee.fee_type}", {'amount': float(amount), 'receipt': receipt_no})
        self.session.commit()
        return True

    def analytics(self) -> dict:
        """مالیاتی تجزیہ اور چارٹ ڈیٹا مہیا کرنا۔"""
        # پچھلے 7 دنوں کا ڈیٹا
        end_date = dt_date.today()
        start_date = end_date - timedelta(days=6)
        
        labels = []
        income_data = []
        expense_data = []
        
        current = start_date
        while current <= end_date:
            labels.append(current.strftime('%d %b'))
            
            inc = self.session.exec(select(func.sum(Income.amount)).where(Income.inst_id == self.institution.id, Income.date == current)).one() or 0
            exp = self.session.exec(select(func.sum(Expense.amount)).where(Expense.inst_id == self.institution.id, Expense.date == current)).one() or 0
            
            income_data.append(float(inc))
            expense_data.append(float(exp))
            current += timedelta(days=1)
            
        return {
            'chart_data': {
                'labels': labels,
                'income': income_data,
                'expense': expense_data
            }
        }

    def _check_access(self):
        if not self.user: raise HTTPException(status_code=401, detail="Auth required.")
        if getattr(self.user, 'is_superuser', False): return True
        if not self.institution: raise HTTPException(status_code=404, detail="Institution missing.")
        
        is_owner = (self.user.id == self.institution.user_id)
        is_staff = hasattr(self.user, 'staff') and self.user.staff and (self.user.staff.inst_id == self.institution.id)
        
        if not (is_owner or is_staff):
            raise HTTPException(status_code=403, detail="Finance access denied.")
        return True

    @staticmethod
    def run_global_monthly_generation(session: Session):
        """تمام اداروں کے لیے خودکار طور پر ماہانہ فیسیں جنریٹ کرنے کا گلوبل ہینڈلر۔"""
        try:
            now = dt_date.today()
            target_month = now.replace(day=1)
            # Loop for all active institutions
            institutions = session.exec(select(Institution)).all()
            for inst in institutions:
                # Bypass access check for system task
                from app.models import Admission, Fee, Student
                
                # Get all active admissions for this institution
                admissions_stmt = select(Admission).join(Student).where(
                    Student.inst_id == inst.id,
                    Admission.status == 'active'
                )
                active_admissions = session.exec(admissions_stmt).all()
                
                count = 0
                for ad in active_admissions:
                    # Check if fee already exists for this admission this month
                    exists = session.exec(select(Fee).where(
                        Fee.admission_id == ad.id,
                        Fee.month == target_month,
                        Fee.fee_type == 'monthly'
                    )).first()
                    
                    if not exists:
                        session.add(Fee(
                            inst_id=inst.id,
                            student_id=ad.student_id,
                            admission_id=ad.id,
                            course_id=ad.course_id,
                            fee_type='monthly',
                            amount_due=ad.agreed_course_fee or 0,
                            title=f"Monthly Fee ({now.strftime('%B %Y')})",
                            due_date=now.replace(day=10),
                            month=target_month,
                            status='Pending'
                        ))
                        count += 1
                
                if count > 0:
                    AuditManager.log_activity(session, inst.id, 0, 'auto_generate_global', 'System', 0, f"Generated {count} monthly fees", {'month': target_month.isoformat()})
                    
            session.commit()
        except Exception as e:
            print(f"B-Task Error: {e}")
            session.rollback()
    def get_institution_financial_summary(self):
        """پورے ادارے کے مالیاتی اعداد و شمار کا مجموعہ۔"""
        self._check_access()
        from app.models import Fee, Course, Income, Expense
        from sqlalchemy import func
        
        # 1. Total Income & Expense (Current Month)
        today = dt_date.today()
        start_of_month = today.replace(day=1)
        
        total_income = self.session.exec(select(func.sum(Income.amount)).where(Income.inst_id == self.institution.id, Income.date >= start_of_month)).one() or 0
        total_expense = self.session.exec(select(func.sum(Expense.amount)).where(Expense.inst_id == self.institution.id, Expense.date >= start_of_month)).one() or 0
        
        # 2. Receivables (Pending Fees)
        total_pending = self.session.exec(select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
            Fee.inst_id == self.institution.id, Fee.status.in_(['Pending', 'Partial'])
        )).one() or 0
        
        # 3. Income per Course (Breakdown)
        course_stats = []
        courses = self.session.exec(select(Course).where(Course.inst_id == self.institution.id)).all()
        for c in courses:
            c_income = self.session.exec(select(func.sum(Fee.amount_paid)).where(Fee.course_id == c.id, Fee.month >= start_of_month)).one() or 0
            c_pending = self.session.exec(select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
                Fee.course_id == c.id, Fee.status.in_(['Pending', 'Partial'])
            )).one() or 0
            course_stats.append({
                "id": c.id,
                "title": c.title,
                "income": float(c_income),
                "pending": float(c_pending)
            })
            
        return {
            "total_income": float(total_income),
            "total_expense": float(total_expense),
            "total_pending": float(total_pending),
            "course_stats": course_stats
        }

    def get_family_financial_report(self):
        """خاندان کے اعتبار سے مالیاتی رپورٹ (Family Wise Ledger)۔"""
        self._check_access()
        from app.models import Parent, Fee
        from sqlalchemy import func
        
        parents = self.session.exec(select(Parent).where(Parent.inst_id == self.institution.id)).all()
        family_report = []
        
        for p in parents:
            student_ids = [s.id for s in p.students]
            if not student_ids: continue
            
            total_pending = self.session.exec(select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
                Fee.student_id.in_(student_ids),
                Fee.status.in_(['Pending', 'Partial'])
            )).one() or 0
            
            family_report.append({
                "family_id": p.family_id,
                "parent_name": p.name,
                "mobile": p.mobile,
                "student_count": len(student_ids),
                "total_pending": float(total_pending)
            })
            
        # Sort by pending dues (highest first)
        family_report.sort(key=lambda x: x['total_pending'], reverse=True)
        return family_report
