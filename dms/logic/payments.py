from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
import random

from ..models import (
    Fee, Fee_Payment, WalletTransaction, Income, Expense, 
    Student, Staff
)

# ============================================================
# 1. CASHIER CLASS (Transactions - In/Out)
# ============================================================
class Cashier:
    def __init__(self, institution, user):
        self.institution = institution
        self.user = user

    @transaction.atomic
    def collect_fee(self, student_id=None, fee_id=None, amount=0, method="Cash", use_wallet=False):
        """طالب علم سے فیس وصول کرنا (Waterfall Logic)"""
        amount = Decimal(str(amount or 0))
        student = self._get_student(fee_id, student_id)
        if not student: return {"status": "error", "message": "Student not found"}

        receipts = []
        remaining_cash = amount
        pending_fees = self._get_pending_fees(student)

        # Step A: Wallet Use
        if use_wallet and student.wallet_balance > 0:
            for fee in pending_fees:
                if fee.balance <= 0: continue
                wallet_deduct = min(student.wallet_balance, fee.balance)
                if wallet_deduct > 0:
                    p_rec = self._process_single_payment(student, fee, wallet_deduct, "Wallet", is_wallet=True)
                    self._update_wallet(student, wallet_deduct, "debit", f"Paid {fee.fee_type}", p_rec)
                    receipts.append(p_rec.receipt_number)

        # Step B: Cash Use
        if remaining_cash > 0:
            for fee in pending_fees:
                fee.refresh_from_db()
                if fee.balance <= 0: continue
                if remaining_cash <= 0: break
                pay_amount = min(remaining_cash, fee.balance)
                p_rec = self._process_single_payment(student, fee, pay_amount, method)
                receipts.append(p_rec.receipt_number)
                remaining_cash -= pay_amount

        # Step C: Surplus to Wallet
        if remaining_cash > 0:
            w_rec = self._deposit_to_wallet(student, remaining_cash, method)
            receipts.append(w_rec.receipt_number)

        return {
            "status": "success", "result": {"record_id": receipts[0] if receipts else "N/A", "method": method},
            "student": student, "amount": amount, "wallet_balance": student.wallet_balance
        }

    @transaction.atomic
    def pay_salary(self, staff_id, amount, month_date=None, notes=""):
        """اسٹاف کو تنخواہ دینا"""
        staff = get_object_or_404(Staff, id=staff_id, institution=self.institution)
        amount = Decimal(str(amount))
        desc = f"Salary: {staff.full_name}" + (f" ({month_date.strftime('%B %Y')})" if month_date else "")
        exp = Expense.objects.create(institution=self.institution, amount=amount, category=Expense.Category.SALARY, description=desc + f" {notes}")
        return {"status": "success", "receipt_id": exp.id, "amount": amount}

    # --- Cashier Internal Helpers ---
    def _get_student(self, f_id, s_id):
        if f_id: return get_object_or_404(Fee, id=f_id, institution=self.institution).student
        return get_object_or_404(Student, id=s_id, institution=self.institution)

    def _get_pending_fees(self, student):
        fees = Fee.objects.filter(student=student, institution=self.institution).annotate(paid_sum=Sum('payments__amount')).filter(Q(paid_sum__lt=F('amount_due') + F('late_fee') - F('discount')) | Q(paid_sum__isnull=True))
        return sorted(fees, key=lambda x: (0 if x.fee_type == Fee.FeeType.ADMISSION else 1, x.due_date))

    def _process_single_payment(self, student, fee, amount, method, is_wallet=False):
        p_rec = Fee_Payment.objects.create(institution=self.institution, student=student, fee=fee, amount=amount, payment_method=method)
        if not is_wallet:
            Income.objects.create(institution=self.institution, amount=amount, source="Fee", description=f"Fee ({fee.fee_type}) - {student.full_name}", payment_record=p_rec)
        fee.update_amount_paid()
        return p_rec

    def _update_wallet(self, student, amount, t_type, desc, payment_ref=None):
        WalletTransaction.objects.create(student=student, amount=amount, transaction_type=t_type, description=desc, payment_ref=payment_ref)
        if t_type == "credit": student.wallet_balance += amount
        else: student.wallet_balance -= amount
        student.save(update_fields=['wallet_balance'])

    def _deposit_to_wallet(self, student, amount, method):
        dummy_p = Fee_Payment.objects.create(institution=self.institution, student=student, amount=amount, payment_method=method)
        self._update_wallet(student, amount, "credit", f"Advance (Ref: {dummy_p.receipt_number})", dummy_p)
        Income.objects.create(institution=self.institution, amount=amount, source="Fee", description=f"Advance from {student.full_name}", payment_record=dummy_p)
        return dummy_p

def generate_transaction_id(institution, type_tag="REC", reference_user=None):
    """
    Centralized Transaction ID Generator
    Format: [REG_ID]-[PERSON_ID]-[TYPE]-[TIMESTAMP]
    Example: MDR001-S005-FEE-240218
             MDR001-OUT-240218 (If no person attached)
    """
    # 1. Institution Part
    inst_part = "INS"
    if institution:
        if hasattr(institution, 'reg_id') and institution.reg_id:
             inst_part = institution.reg_id.replace("-", "")

    # 2. Person Part (Optional)
    person_part = ""
    if reference_user:
        # Try to get reg_id or id
        if hasattr(reference_user, 'reg_id') and reference_user.reg_id:
            raw_id = reference_user.reg_id
            parts = raw_id.split('-')
            if len(parts) > 2:
                # Optimized: MDR-001-S-005 -> S005
                person_part = f"{parts[-2]}{parts[-1]}-"
            else:
                person_part = f"{raw_id}-"
        else:
            person_part = f"U{reference_user.pk}-"
    
    timestamp = timezone.now().strftime('%y%m%d%H%M%S')
    rand = f"{random.randint(1000, 9999)}"
    return f"{inst_part}-{person_part}{type_tag}-{timestamp}-{rand}"