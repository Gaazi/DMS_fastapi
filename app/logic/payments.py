from decimal import Decimal
from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, and_, or_
from datetime import datetime, date
import random
from fastapi import HTTPException

# Models
from app.models import (
    Fee, Fee_Payment, WalletTransaction, Income, Expense, 
    Student, Staff, Institution
)
from app.logic.audit import AuditLogic

# ============================================================
# 1. CASHIER CLASS (Transactions - In/Out) (FastAPI Version)
# ============================================================
class Cashier:
    def __init__(self, session: Session, institution: Institution, user: Any):
        self.session = session
        self.institution = institution
        self.user = user

    def collect_fee(self, student_id: Optional[int] = None, fee_id: Optional[int] = None, 
                    admission_id: Optional[int] = None,
                    amount: float = 0, method: str = "Cash", use_wallet: bool = False):
        """طالب علم سے فیس وصول کرنا (Waterfall Logic)"""
        amount_dec = Decimal(str(amount or 0))
        student = self._get_student(fee_id, student_id)
        if not student: 
            raise HTTPException(status_code=404, detail="Student not found")

        receipts = []
        remaining_cash = amount_dec
        pending_fees = self._get_pending_fees(student, admission_id=admission_id)

        # Step A: Wallet Use
        if use_wallet and student.wallet_balance > 0:
            for fee in pending_fees:
                balance = (fee.amount_due + fee.late_fee - fee.discount) - fee.amount_paid
                if balance <= 0: continue
                
                wallet_deduct = min(student.wallet_balance, balance)
                if wallet_deduct > 0:
                    p_rec = self._process_single_payment(student, fee, wallet_deduct, "Wallet", is_wallet=True)
                    self._update_wallet(student, wallet_deduct, "debit", f"Paid {fee.fee_type}", p_rec)
                    receipts.append(p_rec.receipt_number)

        # Step B: Cash Use
        if remaining_cash > 0:
            for fee in pending_fees:
                self.session.refresh(fee)
                balance = (fee.amount_due + fee.late_fee - fee.discount) - fee.amount_paid
                
                if balance <= 0: continue
                if remaining_cash <= 0: break
                
                pay_amount = min(remaining_cash, balance)
                p_rec = self._process_single_payment(student, fee, pay_amount, method)
                receipts.append(p_rec.receipt_number)
                remaining_cash -= pay_amount

        # Step C: Surplus to Wallet
        if remaining_cash > 0:
            w_rec = self._deposit_to_wallet(student, remaining_cash, method)
            receipts.append(w_rec.receipt_number)

        # آڈٹ لاگنگ
        AuditLogic.log_activity(
            self.session, self.institution.id, self.user.id, 
            'collect_fee', 'Student', student.id, 
            f"Received {amount} from {student.name}", 
            {'receipts': receipts, 'amount': amount}
        )

        self.session.commit()

        return {
            "status": "success", 
            "result": {"record_id": receipts[0] if receipts else "N/A", "method": method},
            "student": student, 
            "amount": amount_dec, 
            "wallet_balance": student.wallet_balance
        }

    def collect_family_fee(self, family_id: str, amount: float, method: str = "Cash"):
        """خاندان (Family) کی بنیاد پر تمام طلبہ کی فیس وصول کرنا اور تقسیم کرنا۔"""
        from app.models import Parent
        parent = self.session.exec(select(Parent).where(func.lower(Parent.family_id) == family_id.lower(), Parent.inst_id == self.institution.id)).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Family record not found")
            
        all_students = parent.students
        amount_dec = Decimal(str(amount or 0))
        remaining_cash = amount_dec
        receipts = []
        
        # Aggregate all pending fees for all children
        all_pending_fees = []
        for student in all_students:
            all_pending_fees.extend(self._get_pending_fees(student))
            
        # Sort by date (oldest first) across all children
        all_pending_fees.sort(key=lambda f: f.due_date or date.max)
        
        for fee in all_pending_fees:
            if remaining_cash <= 0: break
            student = next(s for s in all_students if s.id == fee.student_id)
            
            balance = (fee.amount_due + fee.late_fee - fee.discount) - fee.amount_paid
            if balance <= 0: continue
            
            pay_amount = min(remaining_cash, balance)
            p_rec = self._process_single_payment(student, fee, pay_amount, method)
            receipts.append(p_rec.receipt_number)
            remaining_cash -= pay_amount
            
        # If surplus, add to the first student's wallet
        if remaining_cash > 0 and all_students:
            w_rec = self._deposit_to_wallet(all_students[0], remaining_cash, method)
            receipts.append(w_rec.receipt_number)
            
        self.session.commit()
        return {
            "status": "success",
            "receipts": receipts,
            "total_paid": amount_dec,
            "remaining_surplus": remaining_cash,
            "parent": parent,
            "students": all_students
        }

    def pay_salary(self, staff_id: int, amount: float, month_date: Optional[date] = None, notes: str = ""):
        """اسٹاف کو تنخواہ دینا food"""
        from app.logic.staff import StaffLogic
        sm = StaffLogic(self.user, self.session)
        staff = self.session.get(Staff, staff_id)
        if not staff or staff.inst_id != self.institution.id:
            raise HTTPException(status_code=404, detail="Staff not found")
            
        amount_dec = Decimal(str(amount))
        sm.target = staff 
        
        from app.logic.finance import FinanceLogic
        fm = FinanceLogic(self.session, self.institution, self.user)
        
        desc = f"Salary: {staff.name}" + (f" ({month_date.strftime('%B %Y')})" if month_date else "")
        expense = fm.record_expense(
            category="salary",
            amount=amount_dec,
            description=f"{desc} {notes}"
        )
        
        # نوٹ: fm.record_expense پہلے ہی آڈٹ لاگ اور کمٹ کر چکا ہے
        return {"status": "success", "receipt_id": expense.id, "amount": amount_dec}


    # --- Cashier Internal Helpers ---
    def _get_student(self, f_id, s_id):
        if f_id:
            fee = self.session.get(Fee, f_id)
            if not fee: return None
            return self.session.get(Student, fee.student_id)
        return self.session.get(Student, s_id)

    def _get_pending_fees(self, student: Student, admission_id: Optional[int] = None) -> List[Fee]:
        # بقایا فیسیں حاصل کریں (جہاں ادا شدہ رقم کل واجبات سے کم ہو)
        stmt = select(Fee).where(
            Fee.student_id == student.id,
            Fee.inst_id == self.institution.id,
            Fee.status.in_(['Pending', 'Partial'])
        )
        all_pending = self.session.exec(stmt).all()
        
        # Sort logic: 
        # 1. If admission_id is provided, prioritize it
        # 2. Admission fees before regular fees
        # 3. Oldest first
        def sort_key(f):
            priority = 0
            if admission_id and f.admission_id == admission_id: priority = -10
            type_weight = 0 if f.fee_type == "admission" else 1
            return (priority, type_weight, f.due_date or date.max)

        return sorted(all_pending, key=sort_key)

    def _process_single_payment(self, student: Student, fee: Fee, amount: Decimal, method: str, is_wallet: bool = False):
        p_rec = Fee_Payment(
            inst_id=self.institution.id, 
            student_id=student.id, 
            fee_id=fee.id, 
            amount=amount, 
            payment_method=method,
            receipt_number=generate_transaction_id(self.institution, "REC", student)
        )
        self.session.add(p_rec)
        self.session.flush() # ID حاصل کرنے کے لیے

        if not is_wallet:
            income = Income(
                inst_id=self.institution.id, 
                amount=amount, 
                source="Fee", 
                description=f"Fee ({fee.fee_type}) - {student.name}", 
                payment_record_id=p_rec.id,
                receipt_number=p_rec.receipt_number
            )
            self.session.add(income)
        
        # فیس کی ادا شدہ رقم اپڈیٹ کریں
        # SQLite stores Float as native Python float; cast to Decimal to avoid TypeError
        current_paid = Decimal(str(fee.amount_paid or 0))
        amount_due = Decimal(str(fee.amount_due or 0))
        late_fee_val = Decimal(str(fee.late_fee or 0))
        discount_val = Decimal(str(fee.discount or 0))
        
        fee.amount_paid = current_paid + amount
        if fee.amount_paid >= (amount_due + late_fee_val - discount_val):
            fee.status = "Paid"
        else:
            fee.status = "Partial"
            
        self.session.add(fee)
        return p_rec

    def _update_wallet(self, student: Student, amount: Decimal, t_type: str, desc: str, payment_ref: Fee_Payment = None):
        trans = WalletTransaction(
            student_id=student.id, 
            amount=amount, 
            transaction_type=t_type, 
            description=desc, 
            payment_ref_id=payment_ref.id if payment_ref else None
        )
        self.session.add(trans)
        
        if t_type == "credit": 
            student.wallet_balance += amount
        else: 
            student.wallet_balance -= amount
            
        self.session.add(student)

    def _deposit_to_wallet(self, student: Student, amount: Decimal, method: str):
        # والٹ میں جمع کی گئی رقم کو براہ راست آمدن کے طور پر ریکارڈ کریں
        # یہاں Fee_Payment بنانے کے بجائے ہم براہ راست ٹرانزیکشن ریکارڈ کرتے ہیں
        # تاکہ ماڈل کے فیس آئی ڈی کی پابندی سے بچا جا سکے
        
        income = Income(
            inst_id=self.institution.id, 
            amount=amount, 
            source="Wallet Deposit", 
            description=f"Advance / Wallet Deposit: {student.name}", 
            receipt_number=generate_transaction_id(self.institution, "WAL", student)
        )
        self.session.add(income)
        self.session.flush()

        self._update_wallet(student, amount, "credit", f"Wallet Deposit (Ref: {income.receipt_number})", None)
        
        return income # اب ہم انکم آبجیکٹ واپس کر رہے ہیں جس میں رسیٹ نمبر ہے


def generate_transaction_id(institution: Institution, type_tag: str = "REC", person: Any = None):
    """رابطہ کوڈ اور ٹائم اسٹیمپ کے ساتھ یونیک ٹرانزیکشن آئی ڈی بنانا۔"""
    inst_part = "INS"
    if institution:
        if hasattr(institution, 'reg_id') and institution.reg_id:
             inst_part = str(institution.reg_id).replace("-", "").upper()
        elif hasattr(institution, 'slug') and institution.slug:
             inst_part = institution.slug[:3].upper()

    person_part = ""
    if person:
        person_id = getattr(person, 'reg_id', None) or getattr(person, 'id', '0')
        person_part = f"{str(person_id).replace('-', '')}-"
    
    timestamp = datetime.now().strftime('%y%m%d%H%M')
    rand = f"{random.randint(100, 999)}"
    return f"{inst_part}-{person_part}{type_tag}-{timestamp}{rand}"