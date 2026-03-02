from decimal import Decimal
from itertools import chain
from operator import attrgetter
from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator

from django.urls import reverse
from ..models import (
    Institution, Student, Enrollment, Fee, Fee_Payment, 
    Income, Expense, WalletTransaction, Donor, Staff
)
from .permissions import InstitutionAccess
from .payments import Cashier

class FinanceManager:
    def __init__(self, user, student=None, institution=None):
        self.user = user
        self.student = student
        self.institution = institution
        
        if not self.institution:
            if self.student: self.institution = self.student.institution
            elif hasattr(user, 'staff'): self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'): self.institution = user.institution_set.first()

        # System Access (e.g. Management Commands) bypasses permission check
        if self.user:
            # Allow students to view their own finance records without finance manager access
            if self.student and hasattr(self.user, 'student') and self.user.student == self.student:
                pass
            else:
                access = InstitutionAccess(self.user, self.institution)
                # Allow academic staff to view specific student finance data
                if self.student and access.can_view_academics():
                    pass
                else:
                    access.enforce_finance_access()

    def set_student(self, student):
        """Allow switching context to a specific student dynamically."""
        self.student = student
        return self

    def record_expense(self, category, amount, description, **kwargs):
        """Programmatically record an expense."""
        from django.utils import timezone
        
        paid_by = kwargs.get('paid_by', '')
        if paid_by:
            description = f"{description} ({paid_by})"
            
        return Expense.objects.create(
            institution=self.institution,
            category=category,
            amount=amount,
            description=description,
            date=timezone.now().date()
        )

        
    # --- Payment Bridge (Calls Cashier) ---
    def pay(self, **kwargs):
        """Delegates payment logic to Cashier"""
        cashier = Cashier(self.institution, self.user)
        response = cashier.collect_fee(**kwargs)
        # UI Compatibility: Ensure currency label is present for receipts
        response['currency'] = self.currency()
        return response

    # --- Reports & Analytics ---
    def institution_summary(self, start_date=None, end_date=None):
        filters = Q(institution=self.institution)
        if start_date and end_date: filters &= Q(date__range=[start_date, end_date])
        inc = Income.objects.filter(filters).aggregate(total=Sum('amount'), count=Count('id'))
        exp = Expense.objects.filter(filters).aggregate(total=Sum('amount'), count=Count('id'))
        total_in = inc['total'] or Decimal('0.00')
        total_out = exp['total'] or Decimal('0.00')
        return {
            'total_amount': total_in, 
            'donation_count': inc['count'] or 0, 
            'total_expenses': total_out, 
            'balance': total_in - total_out,
            'total_entries': (inc['count'] or 0) + (exp['count'] or 0),
            'revenue': {'total': total_in, 'count': inc['count'] or 0}
        }

    def analytics(self, months=6, page=1):
        # 1. Chart Data
        inc_m = Income.objects.filter(institution=self.institution).annotate(m=TruncMonth('date')).values('m').annotate(t=Sum('amount')).order_by('-m')[:months]
        exp_m = Expense.objects.filter(institution=self.institution).annotate(m=TruncMonth('date')).values('m').annotate(t=Sum('amount')).order_by('-m')[:months]
        
        # 2. Ledger (Passbook Logic) with Pagination
        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1
            
        per_page = 20
        # Calculate limit: fetch enough to cover up to the end of the current page
        fetch_limit = page * per_page
        
        # Fetch top 'fetch_limit' records from both tables
        # Note: We fetch 'fetch_limit' from EACH to ensure that after merging and sorting,
        # we definitely have at least 'fetch_limit' valid top transactions combined.
        # HARD CAP MEMORY PROTECTION: Prevent fetching more than 500 records to avoid RAM explosion
        MAX_SAFE_FETCH = 500
        safe_fetch_limit = min(fetch_limit, MAX_SAFE_FETCH)
        
        incomes = list(Income.objects.filter(institution=self.institution).select_related('donor', 'payment_record__student').order_by('-date', '-id')[:safe_fetch_limit])
        expenses = list(Expense.objects.filter(institution=self.institution).order_by('-date', '-id')[:safe_fetch_limit])
        
        # Tagging for Template
        for i in incomes: 
            i.transaction_type = 'income'
            if i.donor:
                i.related_url = reverse('donor_detail', args=[self.institution.slug, i.donor.id])
            elif i.payment_record and i.payment_record.student:
                i.related_url = reverse('student_detail', args=[self.institution.slug, i.payment_record.student.id])
                
        for e in expenses: 
            e.transaction_type = 'expense'
            # Link to the general expense list as there is no expense detail view yet
            e.related_url = reverse('expense', args=[self.institution.slug])
        
        # Merge and sort by date descending
        # We take only up to 'safe_fetch_limit' because those are the guaranteed correct global order top items
        all_ledger_upto_page = sorted(chain(incomes, expenses), key=attrgetter('date', 'id'), reverse=True)[:safe_fetch_limit]
        
        # Calculate Running Balance (Backwards from Current Balance)
        summary = self.institution_summary()
        current_running_balance = summary['balance'] # Start with current total
        
        final_ledger_context = []
        
        # Determine the start/end indices for the requested page within our fetched list
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Iterate through ALL fetched items to maintain correct running balance calculation
        for idx, entry in enumerate(all_ledger_upto_page):
            # Assign balance *after* this transaction (which is current state moving backwards)
            entry.running_balance = current_running_balance
            
            # Logic for next iteration (calculating previous balance)
            if entry.transaction_type == 'income':
                current_running_balance -= entry.amount
            else:
                current_running_balance += entry.amount
            
            # If this item is within our requested page range, add it to result
            if start_idx <= idx < end_idx:
                final_ledger_context.append(entry)

        # Pagination Object Construction
        # We simulate a Paginator by using the total counts
        total_incomes = Income.objects.filter(institution=self.institution).count()
        total_expenses = Expense.objects.filter(institution=self.institution).count()
        total_items = total_incomes + total_expenses
        
        # Create a dummy list of total size to fool Paginator, or just use range
        # We cap the paginator to our MAX_SAFE_FETCH so users don't see empty pages if they skip to page 100
        effective_total_items = min(total_items, MAX_SAFE_FETCH)
        paginator = Paginator(range(effective_total_items), per_page)
        try:
            page_obj = paginator.page(page)
        except:
            page_obj = paginator.page(1)

        return {
            'chart_data': {
                'labels': [m['m'].strftime('%b') for m in reversed(inc_m)], 
                'income': [float(m['t']) for m in reversed(inc_m)], 
                'expense': [float(m['t']) for m in reversed(exp_m or [])]
            },
            'recent_transactions': final_ledger_context,
            'page_obj': page_obj
        }

    def income(self, request=None):
        summary = self.institution_summary()
        donations_qs = Income.objects.filter(institution=self.institution).select_related('donor').order_by('-date', '-id')
        
        page_obj = None
        if request:
            page = request.GET.get('page', 1)
            paginator = Paginator(donations_qs, 20)
            try:
                page_obj = paginator.page(page)
            except:
                page_obj = paginator.page(1)
            donations = page_obj
        else:
            # Fallback for non-request usage or if not provided
            donations = donations_qs[:20]

        total = summary['total_amount']
        count = summary['donation_count']
        average = total / count if count > 0 else 0
        return {
            **summary, 
            "average_amount": average,
            "latest_income": donations_qs.first(),
            "incomes": donations, 
            "currency_label": self.currency(),
             "institution": self.institution,
             "page_obj": page_obj # Expose page_obj for template consistency
        }

    def expenses(self, request):
        summary = self.institution_summary()
        expenses = Expense.objects.filter(institution=self.institution).order_by('-date')
        page_obj = Paginator(expenses, 20).get_page(request.GET.get('page'))
        return {
            **summary, 
            "expenses": page_obj, 
            "currency_label": self.currency(),
            "institution": self.institution
        }
    
    def balance(self, request):
        """
        Institution balance dashboard context
        (Aggregator / Facade method)
        """
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        summary = self.institution_summary(start_date, end_date)
        analytics = self.analytics(page=request.GET.get('page'))

        return {
            **summary,
            **analytics,
            "institution": self.institution,
            "currency_label": self.currency()
        }

    # --- 8. Form and Action Handlers ---
    def add_entry(self, request, action_type="income"):
        from ..forms import IncomeForm, ExpenseForm
        form_class = IncomeForm if action_type == "income" else ExpenseForm
        form = form_class(request.POST, institution=self.institution) if action_type == "income" else form_class(request.POST)

        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.institution = self.institution
                if action_type == "income" and not obj.donor and form.cleaned_data.get('new_donor_name'):
                    donor, _ = Donor.objects.get_or_create(institution=self.institution, name=form.cleaned_data['new_donor_name'], phone=form.cleaned_data.get('new_donor_phone', ''))
                    obj.donor = donor
                obj.save()
                
            from dms.helper import number_to_words
            is_inc = (action_type == "income")
            main_cat = obj.source if is_inc else obj.category
            method_str = f"{main_cat} - {obj.description}" if obj.description else main_cat

            receipt_data = {
                'result': {'record_id': obj.receipt_number, 'method': method_str},
                'amount': obj.amount,
                'amount_words': number_to_words(obj.amount),
                'currency': self.currency(),
                'message': f"{action_type.capitalize()} ریکارڈ محفوظ ہو گیا",
                'is_expense': not is_inc
            }
            
            if is_inc:
                receipt_data['donor_name'] = obj.donor.name if obj.donor else "Anonymous"
                receipt_data['is_advance'] = False
            
            success_data = {
                "status": "success",
                "message": receipt_data['message'],
                "receipt_context": receipt_data
            }
            return True, success_data, None
        return False, "براہ کرم فارم کی غلطیاں درست کریں", form

    # Global Fee History
    def global_fee_history(self):
        return Fee.objects.filter(institution=self.institution).order_by('-due_date')

    # --- 5. Fee Detail ---
    def fee_detail(self, fee_id):
        fee = get_object_or_404(Fee, id=fee_id, institution=self.institution)
        balance = fee.balance
        from dms.helper import number_to_words
        return {
            'fee': fee, 'student': fee.student, 'balance': balance,
            'history': fee.payments.all().order_by('-payment_date'),
            'amount_in_words': number_to_words(balance),
            'currency_label': self.currency()
        }

    # Student Wallet History
    def student_wallet(self, limit=10):
        if not self.student: return WalletTransaction.objects.none()
        return self.student.wallet_transactions.all().order_by('-date')[:limit]

    # --- 6. Student Specific Methods (For Student Portal) ---
    def student_stats(self):
        if not self.student: return {}
        totals = self.student.fees.aggregate(total_due=Sum(F('amount_due') + F('late_fee') - F('discount')), total_paid=Sum('amount_paid'))
        due, paid = totals['total_due'] or Decimal('0.00'), totals['total_paid'] or Decimal('0.00')
        return {"fee_totals": totals, "fee_balance": (due - paid).quantize(Decimal('0.01')), "first_pending_fee": self.fee_dues().first()}

    def student_fee_history(self):
        """Retrieve the student's complete fee history."""
        if not self.student: return Fee.objects.none()
        return self.student.fees.all().order_by('-due_date')

    def fee_dues(self):
        """List of pending fees that are yet to be paid."""
        if not self.student: return Fee.objects.none()
        return self.student.fees.annotate(
            paid_sum=Sum('payments__amount')
        ).filter(Q(paid_sum__lt=F('amount_due') + F('late_fee') - F('discount')) | Q(paid_sum__isnull=True)).order_by('due_date')

    @staticmethod
    def generate_initial_fees_for_enrollment(enrollment):
        """Generate admission and initial course fees for a new enrollment."""
        inst_type = enrollment.student.institution.type
        
        # Terminology Setup
        term_admission = "Membership Contribution" if inst_type == 'masjid' else "Admission Fee"
        term_monthly = "Monthly Contribution" if inst_type == 'masjid' else "Monthly Fee"
        
        # Always generate admission fee record, even if 0 (for free students)
        adm_title_suffix = " (Free/Waived)" if enrollment.agreed_admission_fee == 0 else ""
        Fee.objects.create(
            institution=enrollment.student.institution,
            student=enrollment.student,
            course=enrollment.course,
            enrollment=enrollment,
            fee_type=Fee.FeeType.ADMISSION,
            amount_due=enrollment.agreed_admission_fee,
            title=f"{term_admission} - {enrollment.course.title}{adm_title_suffix}",
            due_date=timezone.now().date(),
            month=enrollment.fee_start_month,
            status=Fee.Status.WAIVED if enrollment.agreed_admission_fee == 0 else Fee.Status.PENDING
        )
        
        # Always generate course fee record, even if 0
        f_type = Fee.FeeType.MONTHLY if enrollment.course.fee_type == 'monthly' else (Fee.FeeType.INSTALLMENT if enrollment.course.fee_type == 'installment' else Fee.FeeType.COURSE)
        
        # Adjust Title Base
        base_title = term_monthly if f_type == Fee.FeeType.MONTHLY else f_type.capitalize()
        crs_title = f"{enrollment.course.title} - {base_title}"
        
        crs_title_suffix = " (Free/Waived)" if enrollment.agreed_course_fee == 0 else ""
        
        Fee.objects.create(
            institution=enrollment.student.institution,
            student=enrollment.student,
            course=enrollment.course,
            enrollment=enrollment,
            fee_type=f_type,
            amount_due=enrollment.agreed_course_fee,
            title=f"{crs_title}{crs_title_suffix}",
            due_date=enrollment.fee_start_month.replace(day=25) if f_type == Fee.FeeType.MONTHLY else enrollment.fee_start_month,
            month=enrollment.fee_start_month,
            status=Fee.Status.WAIVED if enrollment.agreed_course_fee == 0 else Fee.Status.PENDING
        )

    @transaction.atomic
    def auto_generate_fees(self, year=None, month=None):
        from django.utils import timezone
        
        now_date = timezone.localdate()
        target_date = now_date.replace(year=year or now_date.year, month=month or now_date.month, day=1)
        
        active_enrollments = Enrollment.objects.filter(
            student__institution=self.institution, 
            status='active', 
            course__fee_type='monthly', 
            agreed_course_fee__gt=0, 
            fee_start_month__lte=target_date
        ).exclude(fees__month=target_date, fees__fee_type=Fee.FeeType.MONTHLY)
        
        fee_objs = []
        for e in active_enrollments:
            month_label = f" ({target_date.strftime('%b %Y')})"
            course_label = f" - {e.course.title}" if e.course else ""
            title = f"ماہانہ فیس{course_label}{month_label}" # Monthly Fee mapped strictly
            
            fee_objs.append(Fee(
                institution=self.institution, 
                student=e.student, 
                enrollment=e, 
                course=e.course, 
                fee_type=Fee.FeeType.MONTHLY, 
                amount_due=e.agreed_course_fee, 
                month=target_date, 
                due_date=target_date.replace(day=25),
                title=title,
                status=Fee.Status.PENDING
            ))
            
        if fee_objs:
            Fee.objects.bulk_create(fee_objs)
            
        return len(fee_objs)

    def currency(self):
        from ..logic.institution import InstitutionManager
        return InstitutionManager.get_currency_label(self.institution)
