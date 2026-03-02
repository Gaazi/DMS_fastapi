from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..logic.permissions import get_institution_with_access
from ..models import Income, Expense
from ..forms import IncomeForm, ExpenseForm
from django.utils import timezone
from django.db.models import Sum

@login_required
def income_edit(request, institution_slug, income_id):
    """انکم ریکارڈ میں ترمیم"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    income = get_object_or_404(Income, id=income_id, institution=institution)
    
    # If linked to a fee payment, prevent full editing to avoid inconsistency
    if hasattr(income, 'payment_record') and income.payment_record:
        messages.warning(request, "یہ آمدنی فیس کی ادائیگی سے منسلک ہے۔ براہ کرم فیس کے ریکارڈ سے ترمیم کریں۔")
        return redirect('income_detail', institution_slug=institution.slug, income_id=income.id)

    if request.method == "POST":
        form = IncomeForm(request.POST, instance=income, institution=institution)
        if form.is_valid():
            form.save()
            messages.success(request, "آمدنی کا ریکارڈ اپ ڈیٹ ہو گیا۔")
            return redirect('income_detail', institution_slug=institution.slug, income_id=income.id)
    else:
        form = IncomeForm(instance=income, institution=institution)
    
    return render(request, "dms/income_form.html", {
        "institution": institution,
        "form": form,
        "editing": True,
        "title": f"Edit Income #{income.receipt_number}"
    })

@login_required
def expense_edit(request, institution_slug, expense_id):
    """اخراجات ریکارڈ میں ترمیم"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    expense = get_object_or_404(Expense, id=expense_id, institution=institution)
    
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "اخراجات کا ریکارڈ اپ ڈیٹ ہو گیا۔")
            return redirect('expense_detail', institution_slug=institution.slug, expense_id=expense.id)
    else:
        form = ExpenseForm(instance=expense)
    
    return render(request, "dms/expense_form.html", {
        "institution": institution,
        "form": form,
        "editing": True,
        "title": f"Edit Expense #{expense.receipt_number}"
    })

@login_required
def transaction_report(request, institution_slug):
    """Transaction Report (PDF)"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    # Fetch Expenses (and maybe Income later?)
    expenses = Expense.objects.filter(institution=institution).order_by('-date')
    
    total = expenses.aggregate(t=Sum('amount'))['t'] or 0

    return render(request, "dms/reports/transaction_report.html", {
        "institution": institution,
        "expenses": expenses,
        "total": total,
        "today_date": timezone.now().date()
    })
