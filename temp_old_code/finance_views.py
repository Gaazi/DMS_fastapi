import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from ..logic.finance import FinanceManager
from ..logic.donations import DonationManager
from ..models import Institution, Donor, Income, Expense
from ..forms import IncomeForm, ExpenseForm, PublicSupportForm, DonorForm
from ..logic.permissions import get_institution_with_access

@login_required
def fees(request, institution_slug, fee_id):
    """طالب علم کی فیس کی تفصیلات اور UPI ادائیگی کا صفحہ"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    context = fm.fee_detail(fee_id)
    # Ensure institution is available in template context
    context["institution"] = institution
    return render(request, 'dms/student_detail.html', context)

@login_required
def pay_installment(request, institution_slug, fee_id):
    """HTMX کے ذریعے ادائیگی: فیس یا والٹ (Advance)"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        # ادائیگی پروسیس کریں
        result = fm.pay(
            fee_id=fee_id if fee_id != 0 else None,
            student_id=request.POST.get('student_id'),
            amount=request.POST.get('amount', 0),
            method=request.POST.get('method', 'Cash'),
            use_wallet=request.POST.get('use_wallet') == 'on'
        )
        
        if result['status'] == 'success':
            result['amount_words'] = number_to_words(request.POST.get('amount', 0))
            response = render(request, 'dms/partials/receipt_fee.html', result)
            # HTMX ٹریگرز: ڈیش بورڈ اور ٹیبلز اپ ڈیٹ کرنے کے لیے
            response['HX-Trigger'] = json.dumps({
                "updateBalance": None, 
                "refreshFeeTable": None, 
                "closeModal": None
            })
            return response
            
    return HttpResponse("ادائیگی مکمل نہیں ہوسکی۔", status=400)

@login_required
def balance(request, institution_slug):
    """ادارے کا مالیاتی خلاصہ اور گراف"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    
    context = fm.balance(request)
    # Context already contains "institution" from Manager
    
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'balance-summary-stats':
        return render(request, "dms/partials/balance_summary_partial.html", context)
        
    return render(request, "dms/balance.html", context)

@login_required
def donation(request, institution_slug):
    """آمدنی/عطیات کا ڈیش بورڈ"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    context = fm.income(request)
    
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'income-dashboard-summary':
        return render(request, "dms/partials/income_dashboard_summary_partial.html", context)
        
    return render(request, "dms/income.html", context)

@login_required
def donation_in_create(request, institution_slug):
    """انکم ریکارڈ بنانا"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, msg, form = fm.add_entry(request, "income")
        if success:
            # `msg` اب ایک ڈکشنری ہے
            success_msg = msg['message']
            if request.headers.get('HX-Request'):
                # رسید تیار ہے، بس رینڈر کریں
                response = render(request, "dms/partials/receipt_income.html", msg['receipt_context'])
                response['HX-Trigger'] = json.dumps({"incomeCreated": None, "updateBalance": None})
                return response
            messages.success(request, success_msg)
            return redirect("income", institution_slug=institution.slug)
        # form is already updated with errors from add_entry
    else:
        form = IncomeForm(institution=institution)
        
    context = {"institution": institution, "form": form}
    if request.headers.get('HX-Request'):
        return render(request, "dms/partials/income_form_partial.html", context)
    return render(request, "dms/income_form.html", context)

@login_required
def income_detail(request, institution_slug, income_id):
    """انکم کی تفصیلات"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    income = get_object_or_404(Income, id=income_id, institution=institution)
    
    context = {
        'institution': institution,
        'income': income,
    }
    return render(request, 'dms/income_detail.html', context)

@login_required
def expense(request, institution_slug):
    """اخراجات کی لسٹنگ"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    context = fm.expenses(request)
    # Context already contains "institution" from Manager
    
    if request.headers.get('HX-Request'):
        target = request.headers.get('HX-Target')
        if target == 'expense-summary-container':
            return render(request, "dms/partials/expense_summary_partial.html", context)
        elif target == 'expense-table-container':
            return render(request, "dms/partials/expense_table_partial.html", context)
        elif not request.headers.get('HX-Push-Url'):
            return render(request, "dms/partials/expense_table_partial.html", context)
    return render(request, "dms/expense.html", context)

@login_required
def expense_detail(request, institution_slug, expense_id):
    """اخراجات کی تفصیلات"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    expense = get_object_or_404(Expense, id=expense_id, institution=institution)
    
    context = {
        'institution': institution,
        'expense': expense,
    }
    return render(request, 'dms/expense_detail.html', context)

@login_required
def expense_out_create(request, institution_slug):
    """خرچ ریکارڈ کرنا"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    fm = FinanceManager(request.user, institution=institution)
    
    if request.method == "POST":
        success, msg, form = fm.add_entry(request, "expense")
        if success:
            success_msg = msg['message']
            if request.headers.get('HX-Request'):
                response = render(request, "dms/partials/receipt_expense.html", msg['receipt_context'])
                response['HX-Trigger'] = json.dumps({"expenseCreated": None, "updateBalance": None})
                return response
            messages.success(request, success_msg)
            return redirect("expense", institution_slug=institution.slug)
        # form is already updated with errors from add_entry
    else:
        form = ExpenseForm()
        
    context = {"institution": institution, "form": form}
    if request.headers.get('HX-Request'):
        return render(request, "dms/partials/expense_form_partial.html", context)
    return render(request, "dms/expense_form.html", context)


@login_required
def donation_in_overview(request, institution_slug):
    """عطیات کی تفصیلی فہرست"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    dm = DonationManager(request.user, institution)
    context = dm.get_donation_list_context(page=request.GET.get("page"))
    
    if request.headers.get('HX-Request'):
        target = request.headers.get('HX-Target')
        if target == 'income-summary-stats':
            return render(request, "dms/partials/income_summary_partial.html", context)
        elif target == 'income-table-container':
            return render(request, "dms/partials/income_table_partial.html", context)
        elif not request.headers.get('HX-Push-Url'):
            return render(request, "dms/partials/income_table_partial.html", context)
    return render(request, "dms/income_list.html", context)

@login_required
def donor_detail(request, institution_slug, donor_id):
    """ڈونر کی تفصیلات اور تجزیہ"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    donor = get_object_or_404(Donor, pk=donor_id, institution=institution)
    dm = DonationManager(request.user, institution)
    context = dm.get_donor_analytics(donor)
    context["institution"] = institution
    return render(request, "dms/donor_detail.html", context)

@login_required
def donor_create(request, institution_slug):
    """نیا ڈونر بنانا"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    
    if request.method == "POST":
        form = DonorForm(request.POST)
        if form.is_valid():
            donor = form.save(commit=False)
            donor.institution = institution
            donor.save()
            messages.success(request, f"{donor.name} کو کامیابی سے شامل کر دیا گیا۔")
            return redirect("donor_detail", institution_slug=institution.slug, donor_id=donor.id)
    else:
        form = DonorForm()
    
    return render(request, "dms/donor_form.html", {
        "institution": institution,
        "form": form,
        "title": "Add New Donor"
    })

@login_required
def donor_edit(request, institution_slug, donor_id):
    """ڈونر کی معلومات میں ترمیم"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    donor = get_object_or_404(Donor, pk=donor_id, institution=institution)
    
    if request.method == "POST":
        form = DonorForm(request.POST, instance=donor)
        if form.is_valid():
            form.save()
            messages.success(request, f"{donor.name} کی معلومات اپ ڈیٹ ہو گئیں۔")
            return redirect("donor_detail", institution_slug=institution.slug, donor_id=donor.id)
    else:
        form = DonorForm(instance=donor)
    
    return render(request, "dms/donor_form.html", {
        "institution": institution,
        "form": form,
        "donor": donor,
        "title": f"Edit {donor.name}"
    })

@login_required
def donor_delete(request, institution_slug, donor_id):
    """ڈونر کو حذف کرنا"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    donor = get_object_or_404(Donor, pk=donor_id, institution=institution)
    
    if request.method == "POST":
        donor.delete()
        messages.success(request, "ڈونر کو کامیابی سے حذف کر دیا گیا۔")
        return redirect("donor", institution_slug=institution.slug)
        
    return render(request, "dms/donor_confirm_delete.html", {
        "institution": institution,
        "donor": donor
    })

@login_required
def donor(request, institution_slug):
    """ڈونرز کی فہرست اور مینجمنٹ"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    dm = DonationManager(request.user, institution)
    
    context = dm.get_donor_list_context(page=request.GET.get("page"))
    
    if request.headers.get('HX-Request'):
        target = request.headers.get('HX-Target')
        if target == 'donor-table-container':
            return render(request, "dms/partials/donor_table_partial.html", context)
        elif not request.headers.get('HX-Push-Url'):
             return render(request, "dms/partials/donor_table_partial.html", context)
    return render(request, "dms/donor.html", context)

@login_required
def donor_create_quick(request, institution_slug):
    """انکم فارم سے ڈونر کو فوری محفوظ کرنا (HTMX)"""
    institution, access = get_institution_with_access(institution_slug, request=request, access_type='finance')
    dm = DonationManager(request.user, institution)
    
    success, message, donor = dm.handle_donor_action(request)
    if success:
        response = HttpResponse(f"""
            <div class="flex items-center gap-2 text-emerald-400 text-[10px] font-black uppercase tracking-widest p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20 animate-pulse">
                <i class="fas fa-check-double"></i> {message}
            </div>
        """)
        response['HX-Trigger'] = json.dumps({
            "donor-saved": {"id": donor.id, "name": donor.name},
            "incomeCreated": None 
        })
        return response
    return HttpResponse(message or "نام لکھنا ضروری ہے!", status=400)

def public_donation(request, institution_slug):
    """عوامی عطیہ (بغیر لاگ ان)"""
    institution = get_object_or_404(Institution, slug=institution_slug)
    dm = DonationManager(None, institution)
    
    if request.method == "POST":
        success, message, form = dm.handle_public_donation(request)
        if success:
            messages.success(request, message)
            return render(request, "dms/public_success.html", {"institution": institution})
    else:
        form = PublicSupportForm()
    return render(request, "dms/public_donation.html", {"institution": institution, "form": form})
