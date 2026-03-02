from django.db import transaction, models
from django.db.models import Q, Count, Sum, OuterRef, Subquery, IntegerField, Case, When, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal
import calendar

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: StaffManager (Line 15)
   - Payroll Logic:
     * calculate_payroll (Line 58)
     * process_salary (Line 105)
     * bulk_payroll (Line 150)
   - Management:
     * save_staff (Line 132)
     * delete_staff (Line 122)
     * get_staff_context (Line 194)
"""

class StaffManager:
    """Business logic for Staff members, payroll, and recruitment"""
    
    def __init__(self, user, target=None, institution=None):
        """یوزر، ادارے یا کسی مخصوص اسٹاف ممبر کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        from ..models import Institution, Staff
        
        if isinstance(target, Institution):
            self.institution = target
            self.staff = None
        elif isinstance(target, Staff):
            self.staff = target
            self.institution = target.institution
        else:
            self.staff = None
            self.institution = institution

        # Fallback resolution for institution
        if not self.institution:
            if hasattr(user, 'staff'):
                self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'):
                self.institution = user.institution_set.first()

    def _check_access(self):
        """چیک کرنا کہ کیا یوزر کو اسٹاف مینیجمنٹ اور تنخواہوں کے ریکارڈ تک رسائی حاصل ہے۔"""
        from django.core.exceptions import PermissionDenied
        from .roles import Role
        
        if not self.user or self.user.is_anonymous:
            raise PermissionDenied("Authentication required.")
            
        if self.user.is_superuser:
            return True
            
        if not self.institution:
             raise PermissionDenied("Institution context not found.")

        is_owner = (self.user == self.institution.user)
        staff = getattr(self.user, 'staff', None)
        # 1. Admin/Owner check
        if is_owner or (staff and staff.institution_id == self.institution.id and staff.role == Role.ADMIN.value):
            return True
            
        # 2. Accountant check (View access)
        if staff and staff.institution_id == self.institution.id and staff.role == Role.ACCOUNTANT.value:
            return True
            
        raise PermissionDenied("Access denied to staff management.")

    def calculate_payroll(self, month, year, bonus=Decimal('0.00')):
        """حاضری، غیر حاضری اور لیٹ آمد کی بنیاد پر ماہانہ تنخواہ کا حساب کتاب کرنا۔"""
        if not self.staff:
            return None
            
        from ..models import Staff_Attendance
        attendance = Staff_Attendance.objects.filter(
            staff_member=self.staff, date__month=month, date__year=year
        )
        
        absent_days = attendance.filter(status='absent').count()
        late_days = attendance.filter(is_late=True).count()
        
        base_salary = self.staff.base_salary or Decimal('0.00')
        days_in_month = calendar.monthrange(year, month)[1]
        
        # Salary per day
        per_day = base_salary / Decimal(str(days_in_month))

        # 1. Absence Deduction
        absence_deduction = absent_days * per_day
        
        # 2. Late Deduction (Half day salary for every 3 late arrivals)
        late_deduction = Decimal(str(late_days // 3)) * (per_day / 2)
        
        # 3. Advance Deduction
        advances = self.staff.advances.filter(is_adjusted=False) if hasattr(self.staff, 'advances') else []
        total_advance = Decimal('0.00')
        if hasattr(advances, 'aggregate'):
            total_advance = advances.aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')

        final_payable = (base_salary + bonus) - (absence_deduction + late_deduction + total_advance)
        
        return {
            'base': base_salary,
            'bonus': bonus,
            'deductions': {
                'absence': absence_deduction,
                'late': late_deduction,
                'advance': total_advance,
                'total': absence_deduction + late_deduction + total_advance
            },
            'final': max(Decimal('0.00'), final_payable).quantize(Decimal('1.00')),
            'attendance': {'absent': absent_days, 'late': late_days}
        }

    @transaction.atomic
    def process_salary(self, month, year, bonus=Decimal('0.00')):
        """کسی ملازم کی تنخواہ کو حتمی شکل دینا اور اسے مالیاتی ریکارڈ (Expense) میں درج کرنا۔"""
        self._check_access()
        stats = self.calculate_payroll(month, year, bonus)
        
        from .finance import FinanceManager
        fm = FinanceManager(self.user, institution=self.institution)
        
        fm.record_expense(
            category="salary",
            amount=stats['final'],
            description=f"Salary for {self.staff.name} - {month}/{year}",
            paid_by="Finance Dept"
        )
        
        # 🚨 بگ فکس: سابقہ ایڈوانس رقوم کو "Adjusted" (کٹوت شدہ) کے طور پر مارک کریں
        if hasattr(self.staff, 'advances'):
            self.staff.advances.filter(is_adjusted=False).update(is_adjusted=True)
            
        return True, "Salary has been processed and recorded.", stats

    def delete_staff(self):
        """اسٹاف ممبر کے ریکارڈ کو ڈیٹا بیس سے ختم کرنا (سیکیورٹی چیک کے ساتھ)۔"""
        self._check_access()
        try:
            name = self.staff.name
            self.staff.delete()
            return True, f"Staff member '{name}' has been removed.", None
        except Exception as e:
            return False, f"Error deleting staff: {str(e)}", None

    @transaction.atomic
    def save_staff(self, form, request=None):
        """نئے ملازم کا اندراج کرنا اور اس کا سسٹم یوزر اکاؤنٹ خودکار طور پر بنانا۔"""
        self._check_access()
        try:
            staff = form.save(commit=False)
            staff.institution = self.institution
            staff.save()
            
            # نوٹ: اب یہاں آٹومیٹک اکاؤنٹ نہیں بنے گا۔ انتظامیہ کی ضرورت پر صرف پروفائل پیج سے بنے گا۔
                
            return True, "Staff information has been saved successfully.", staff
        except Exception as e:
            return False, f"Error saving staff: {str(e)}", None

    def process_bulk_payroll(self, month, year):
        """پورے ادارے کے تمام فعال ملازمین کی تنخواہوں کا ایک ساتھ حساب لگانا۔"""
        self._check_access()
        if not self.institution: return []
        
        members = self.institution.staff_set.filter(is_active=True).order_by("name")
        results = []
        
        for member in members:
            results.append({
                'staff': member,
                'report': StaffManager(self.user, member).calculate_payroll(month, year)
            })
        return results

    @transaction.atomic
    def execute_bulk_payroll(self, month, year):
        """تمام فعال ملازمین کی تنخواہیں ایک ساتھ پراسیس کرنا اور ان کے اخراجات درج کرنا۔"""
        self._check_access()
        results = self.process_bulk_payroll(month, year)
        count = 0
        total = Decimal('0.00')
        
        for res in results:
            if res['report'] and res['report']['final'] > 0:
                # مخصوص ممبر کے لیے نیا مینیجر استعمال کریں تاکہ تنخواہ پراسیس ہو سکے
                member_manager = StaffManager(self.user, target=res['staff'])
                member_manager.process_salary(month, year)
                count += 1
                total += res['report']['final']
        
        return True, f"{count} ارکان کی تنخواہیں کامیابی سے ریکارڈ کر دی گئی ہیں (کل رقم: {total})", count

    def get_payroll_context(self, request):
        """پے رول رپورٹ کے صفحے کے لیے تمام ملازمین کی تنخواہوں کا مجموعی ڈیٹا تیار کرنا۔"""
        self._check_access()
        from django.utils import timezone
        month = int(request.GET.get('month', timezone.now().month))
        year = int(request.GET.get('year', timezone.now().year))
        
        results = self.process_bulk_payroll(month, year)
        total_payable = sum(res['report']['final'] for res in results if res['report'])
        
        return {
            "institution": self.institution,
            "results": results,
            "month": month, 
            "year": year,
            "total_payable": total_payable
        }

    def filter_staff(self, query=None):
        """نام یا فون نمبر کی بنیاد پر اسٹاف ممبرز کو تلاش کرنا۔"""
        if not self.institution: return []
        
        from ..models import Staff_Attendance
        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        
        # Attendance Annotations for Staff
        presents_sub = Staff_Attendance.objects.filter(
            staff_member=OuterRef('pk'),
            date__gte=start_of_month,
            status='present'
        ).values('staff_member').annotate(c=Count('id')).values('c')

        absents_sub = Staff_Attendance.objects.filter(
            staff_member=OuterRef('pk'),
            date__gte=start_of_month,
            status='absent'
        ).values('staff_member').annotate(c=Count('id')).values('c')

        staff_members = self.institution.staff_set.select_related('user').all()
        
        staff_members = staff_members.annotate(
            month_presents=Coalesce(Subquery(presents_sub, output_field=IntegerField()), 0),
            month_absents=Coalesce(Subquery(absents_sub, output_field=IntegerField()), 0),
        )

        if query:
            staff_members = staff_members.filter(
                Q(name__icontains=query) | 
                Q(mobile__icontains=query)
            )
        return staff_members.distinct()

    def get_staff_context(self, request, override_form=None):
        """اسٹاف کی فہرست والے صفحے کے لیے تمام ملازمین کا ڈیٹا اور فارم تیار کرنا۔"""
        if not self.institution: return {}
        self._check_access()
        
        from ..models import Staff
        from ..forms import StaffForm

        query = request.GET.get('q')
        edit_id = request.GET.get("edit")
        editing_staff = None
        if edit_id:
            editing_staff = Staff.objects.filter(pk=edit_id, institution=self.institution).first()
            
        staff_members = self.filter_staff(query=query)
        return {
            "institution": self.institution,
            "staff_members": staff_members,
            "query": query,
            "total_count": staff_members.count(),
            "active_count": staff_members.filter(is_active=True).count(),
            "form": override_form or StaffForm(instance=editing_staff),
            "editing_staff": editing_staff
        }

    @transaction.atomic
    def handle_staff_actions(self, request):
        """اسٹاف پیلے سے آنے والے مختلف ایکشنز جیسے ڈیلیٹ یا ایڈٹ کو ہینڈل کرنا۔"""
        self._check_access()
        from ..models import Staff
        from ..forms import StaffForm
        from django.shortcuts import get_object_or_404
        
        action = request.POST.get("action")
        staff_id = request.POST.get("staff_id")
        
        if action == "delete":
            staff_obj = get_object_or_404(Staff, pk=staff_id, institution=self.institution)
            return StaffManager(self.user, staff_obj).delete_staff()
            
        editing_staff = Staff.objects.filter(pk=staff_id, institution=self.institution).first() if staff_id else None
        form = StaffForm(request.POST, instance=editing_staff)
        
        if form.is_valid():
             sm_logic = StaffManager(self.user, institution=self.institution)
             return sm_logic.save_staff(form, request=request)
            
        return False, "Please correct the errors in the form.", form