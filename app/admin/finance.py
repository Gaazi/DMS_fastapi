from app.admin.base import DMSModelView
from app.models.finance import Fee, Fee_Payment, WalletTransaction, Donor, Income, Expense
from app.models.people import StaffAdvance

class FeeAdmin(DMSModelView, model=Fee):
    column_list = [Fee.id, Fee.student_id, Fee.course_id, Fee.amount_due, Fee.amount_paid, Fee.status, Fee.month]
    column_searchable_list = [Fee.status]
    category = "Finance"
    icon = "fa-solid fa-money-check-dollar"

class FeePaymentAdmin(DMSModelView, model=Fee_Payment):
    column_list = [Fee_Payment.id, Fee_Payment.student_id, Fee_Payment.amount, Fee_Payment.payment_method, Fee_Payment.receipt_number, Fee_Payment.payment_date]
    column_searchable_list = [Fee_Payment.receipt_number]
    category = "Finance"
    icon = "fa-solid fa-receipt"

class WalletTransactionAdmin(DMSModelView, model=WalletTransaction):
    column_list = [WalletTransaction.id, WalletTransaction.student_id, WalletTransaction.amount, WalletTransaction.transaction_type, WalletTransaction.date]
    category = "Finance"
    icon = "fa-solid fa-wallet"

class DonorAdmin(DMSModelView, model=Donor):
    column_list = [Donor.id, Donor.name, Donor.phone, Donor.email]
    column_searchable_list = [Donor.name, Donor.phone]
    category = "Finance"
    icon = "fa-solid fa-hand-holding-heart"

class IncomeAdmin(DMSModelView, model=Income):
    column_list = [Income.id, Income.source, Income.amount, Income.date, Income.inst_id]
    category = "Finance"
    icon = "fa-solid fa-arrow-trend-up"

class ExpenseAdmin(DMSModelView, model=Expense):
    column_list = [Expense.id, Expense.category, Expense.amount, Expense.date, Expense.inst_id]
    category = "Finance"
    icon = "fa-solid fa-arrow-trend-down"

class StaffAdvanceAdmin(DMSModelView, model=StaffAdvance):
    column_list = [StaffAdvance.id, StaffAdvance.staff_id, StaffAdvance.amount, StaffAdvance.date, StaffAdvance.is_adjusted]
    category = "Finance"
    icon = "fa-solid fa-money-bill-transfer"
