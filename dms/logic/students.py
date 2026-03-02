from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Count, Sum, OuterRef, Subquery, IntegerField, Case, When, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.paginator import Paginator
from ..models import Institution, Student, Course, Attendance, Fee, Enrollment
from ..forms import StudentForm
from .auth import UserManager

class StudentManager:    
    """
    مرکزی کوآرڈینیٹر (Student Pillar Hub) اور ڈائریکٹری مینیجر
    یہ کلاس تمام سٹوڈنٹ آپریشنز (فہرست، پروفائل، فیس، حاضری) سنبھالتی ہے۔
    """
    def __init__(self, user, target=None, institution=None):
        """طالب علم کے مرکز (Hub) کو یوزر اور ادارے کی معلومات کے ساتھ شروع کرنا۔"""
        self.user = user
        self.institution = institution
        self.student = None

        if isinstance(target, Institution): self.institution = target
        elif isinstance(target, Student):
            self.student = target
            self.institution = target.institution
        
        # ادارہ اور طالب علم سیٹ کرنا
        if not self.institution:
            if hasattr(user, 'staff'): self.institution = user.staff.institution
            elif hasattr(user, 'institution_set'): self.institution = user.institution_set.first()

        if not self.student and hasattr(user, 'student'):
             self.student = user.student
             if self.student and not self.institution: self.institution = self.student.institution

    def _check_access(self, target_student=None):
        """اسٹاف یا طلبہ کی ڈائریکٹری اور ریکارڈز تک رسائی کے حقوق چیک کرنا۔"""
        if self.user.is_superuser: return True
        curr_student = target_student or self.student
        if self.institution:
            is_staff = hasattr(self.user, 'staff') and (self.user.staff.institution == self.institution)
            is_admin = (self.user == self.institution.user)
            if is_staff or is_admin: return True
        if curr_student:
            if hasattr(self.user, 'student') and self.user.student == curr_student: return True
            if hasattr(self.user, 'parent') and curr_student in self.user.parent.students.all(): return True
        raise PermissionDenied("Directory Access Denied.")

    # --- Pillar Accessors ---

    def finance(self): 
        """طالب علم کے مالی معاملات (فیس، والٹ) کے مینیجر تک رسائی۔"""
        from .finance import FinanceManager
        return FinanceManager(self.user, self.student, self.institution)

    def attendance(self): 
        """طالب علم کی حاضری کے مینیجر تک رسائی۔"""
        from .attendance import AttendanceManager
        return AttendanceManager(self.user, institution=self.institution)

    # --- Shared View Logic ---

    def set_student(self, student):
        """موجودہ آپریشن کے لیے ایک مخصوص طالب علم کو منتخب کرنا۔"""
        self.student = student
        return self

    def get_student_list_context(self, request, override_form=None):
        """طلبہ کی فہرست، تلاش کے نتائج، فلٹرز اور مجموعی اعداد و شمار تیار کرنا۔"""
        self._check_access()

        query = request.GET.get('q')
        course_id = request.GET.get('course') # Updated from 'Course'
        students = Student.objects.filter(institution=self.institution).select_related('user')
        
        if query:
            students = students.filter(
                Q(name__icontains=query) | Q(mobile__icontains=query) | Q(reg_id__icontains=query) | Q(enrollments__roll_no__icontains=query)
            ).distinct()
        
        status_val = request.GET.get('status')
        if not status_val:
            status_val = 'active'
            
        if status_val == 'active':
            students = students.filter(is_active=True)
        elif status_val == 'pending':
            students = students.filter(is_active=False, enrollments__status='pending').distinct()
        elif status_val == 'inactive':
            students = students.filter(is_active=False)

        if course_id:
            if status_val == 'active':
                students = students.filter(enrollments__course_id=course_id, enrollments__status='active')
            elif status_val == 'pending':
                students = students.filter(enrollments__course_id=course_id, enrollments__status='pending')
            else:
                # 🚨 بگ فکس: غیر فعال (Inactive) میں وہ طلبہ جن کی یہ کلاس رکی ہوئی یا مکمل ہو چکی ہے
                students = students.filter(enrollments__course_id=course_id, enrollments__status__in=['completed', 'dropped', 'paused'])

        today = timezone.localdate()
        start_of_month = today.replace(day=1)
        
        # Attendance Annotations
        presents_sub = Attendance.objects.filter(
            student=OuterRef('pk'),
            session__date__gte=start_of_month,
            status='present'
        ).values('student').annotate(c=Count('id')).values('c')

        absents_sub = Attendance.objects.filter(
            student=OuterRef('pk'),
            session__date__gte=start_of_month,
            status='absent'
        ).values('student').annotate(c=Count('id')).values('c')

        # Fee Status Annotation
        pending_fee_sub = Fee.objects.filter(
            student=OuterRef('pk'),
        ).exclude(status__in=['Paid', 'Waived']).values('student').annotate(c=Count('id')).values('c')

        pending_amount_sub = Fee.objects.filter(
            student=OuterRef('pk'),
        ).exclude(status__in=['Paid', 'Waived']).values('student').annotate(
            total=Sum(F('amount_due') + F('late_fee') - F('discount') - F('amount_paid'), output_field=DecimalField())
        ).values('total')

        students = students.annotate(
            month_presents=Coalesce(Subquery(presents_sub, output_field=IntegerField()), 0),
            month_absents=Coalesce(Subquery(absents_sub, output_field=IntegerField()), 0),
            has_pending_fee=Coalesce(Subquery(pending_fee_sub, output_field=IntegerField()), 0),
            month_due_amount=Coalesce(Subquery(pending_amount_sub, output_field=DecimalField()), Value(0, output_field=DecimalField()))
        )

        paginator = Paginator(students.order_by('name'), 20)
        page_obj = paginator.get_page(request.GET.get('page'))

        stats = self.institution.student_set.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            inactive=Count('id', filter=Q(is_active=False)),
            today=Count('id', filter=Q(enrollment_date=today))
        )

        # Edit Mode Handling
        edit_id = request.GET.get('edit')
        editing_student = None
        if edit_id and not override_form:
            from ..forms import StudentCreationForm
            editing_student = get_object_or_404(Student, pk=edit_id, institution=self.institution)
            form = StudentCreationForm(instance=editing_student, institution=self.institution)
        else:
            from ..forms import StudentCreationForm  # Local import
            # course_id logic for HTMX/Pre-fill
            course_obj = None
            if course_id:
                course_obj = Course.objects.filter(id=course_id, institution=self.institution).first()
            
            form = override_form or StudentCreationForm(institution=self.institution, course_obj=course_obj)

        return {
            "institution": self.institution,
            "students": page_obj,
            "query": query,
            "courses": Course.objects.filter(institution=self.institution, is_active=True), # Updated key
            "selected_course": course_id, # Updated key
            "existing_students": Student.objects.filter(institution=self.institution).values('name', 'reg_id'),
            "form": form,
            "editing_student": editing_student,
            "total_students": stats['total'],
            "active_students": stats['active'],
            "inactive_students": stats['inactive'],
            "today_added": stats['today'],
        }

    @transaction.atomic
    def save_form(self, form, request=None):
        """نئے یا موجودہ طالب علم کا داخلہ (Enrollment) اور لاگ ان اکاؤنٹ بنانا۔"""
        self._check_access()
        
        from ..logic.permissions import InstitutionAccess
        is_academic_admin = InstitutionAccess(self.user, self.institution).can_manage_academics()
        
        # 1. طالب علم کا تعین کریں (نیا یا پرانا "Hybrid Datalist Logic")
        student = None
        
        if getattr(form, 'instance', None) and form.instance.pk:
            # Edit Mode - موجودہ معلومات کو اپڈیٹ کریں (Status overwrite روکا گیا)
            student = form.save(commit=False)
            student.save()
        else:
            # New Admission Mode
            full_name_input = form.cleaned_data.get('name', '').strip()
            
            # چیک کریں کہ کیا نام "Name [RegID]" فارمیٹ میں ہے؟
            import re
            match = re.match(r"^(.*)\s*\[(\w+)\]$", full_name_input)
            
            if match:
                # اگر فارمیٹ میچ کر گیا، تو رجسٹریشن نمبر سے ڈھونڈیں
                extracted_reg_id = match.group(2).strip()
                
                existing = Student.objects.filter(
                    institution=self.institution, 
                    reg_id=extracted_reg_id
                ).first()
                
                if existing:
                     student = existing
            
            # اگر اب بھی طالب علم نہیں ملا تو نیا بنائیں
            if not student:
                student = form.save(commit=False)
                student.institution = self.institution
                student.is_active = is_academic_admin # True if Admin, False (Pending) if other staff
                student.save()

        # 2. اگر کورس منتخب کیا ہے تو نیا داخلہ (Enrollment) بنائیں
        if hasattr(form, 'cleaned_data') and 'course' in form.cleaned_data and form.cleaned_data.get('course'):
            course = form.cleaned_data['course']
            
            # پرانے ایکٹیو انرولمنٹ کو چیک کریں (تاکہ ڈپلیکیٹ نہ ہو)
            if Enrollment.objects.filter(student=student, course=course, status=Enrollment.Status.ACTIVE).exists():
                return student  # پہلے سے داخل ہے تو کچھ نہ کریں
            
            # رعایت اور فیس (Directly Pass to Model - Model Logic will handle calc)
            enrollment_status = Enrollment.Status.ACTIVE if is_academic_admin else Enrollment.Status.PENDING
            enrollment = Enrollment.objects.create(
                student=student,
                course=course,
                agreed_admission_fee=form.cleaned_data.get('agreed_admission_fee'),
                admission_fee_discount=form.cleaned_data.get('admission_discount'),
                agreed_course_fee=form.cleaned_data.get('agreed_course_fee'),
                course_fee_discount=form.cleaned_data.get('course_discount'),
                fee_start_month=form.cleaned_data.get('fee_start_month'),
                fee_type_override=form.cleaned_data.get('custom_fee_type'),
                status=enrollment_status
            )
            # Note: Enrollment.save() will trigger fee generation via FinanceManager.generate_initial_fees_for_enrollment

            # 3. Initial Payment Handling
            initial_amount = form.cleaned_data.get('initial_payment') or 0
            if initial_amount > 0:
                payment_method = form.cleaned_data.get('payment_method') or 'Cash'
                # Use FinanceManager -> Cashier to process payment against newly generated fees
                fm = self.finance().set_student(student)
                fm.pay(amount=initial_amount, method=payment_method, student_id=student.id)

        return student

    def handle_student_list_actions(self, request):
        """فہرست والے صفحے سے ہونے والے مختلف کاموں (حذف کرنا یا محفوظ کرنا) کو ہینڈل کرنا۔"""
        action = request.POST.get("action")
        student_id = request.POST.get("student_id")
        
        from ..logic.permissions import InstitutionAccess
        is_academic_admin = InstitutionAccess(self.user, self.institution).can_manage_academics()
        
        if action == "delete":
             if not is_academic_admin:
                 return False, "آپ کو ریکارڈ حذف کرنے کی اجازت نہیں ہے۔", None
             self._check_access()
             student = get_object_or_404(Student, pk=student_id, institution=self.institution)
             name = student.name
             student.delete()
             term = "ممبر" if self.institution.type == 'masjid' else "طالب علم"
             return True, f"{term} '{name}' کو حذف کر دیا گیا ہے۔", None
             
        instance = None
        if student_id:
             if not is_academic_admin:
                 return False, "آپ کو پرانے ریکارڈ میں ترمیم کرنے کی اجازت نہیں ہے۔", None
             # ترمیم (Edit Mode) - سادہ StudentForm استعمال کریں
             instance = get_object_or_404(Student, pk=student_id, institution=self.institution)
             form = StudentForm(request.POST, instance=instance, institution=self.institution)
        else:
             # نیا داخلہ (New Admission) - StudentCreationForm استعمال کریں
             from ..forms import StudentCreationForm
             form = StudentCreationForm(request.POST, institution=self.institution)

        if form.is_valid():
            self.save_form(form, request=request)
            return True, "معلومات محفوظ کر لی گئی ہیں۔", None
            
        return False, "غلطیاں درست کریں۔", form

    def update_status(self, is_active):
        """طالب علم کو فعال (Active) یا غیر فعال (Inactive) کرنے کی منطق۔"""
        self._check_access()
        if self.student:
            self.student.is_active = is_active
            self.student.save(update_fields=['is_active'])
            
            if is_active:
                # فعال کرنے پر، زیر التوا (Pending) اور روکے ہوئے (Paused) داخلوں کو ایکٹیو کر دیں
                self.student.enrollments.filter(status__in=['pending', 'paused']).update(status='active')
            else:
                # 🚨 بگ فکس: غیر فعال کرنے پر جاری داخلوں کو (Paused) کر دیں تاکہ ماہانہ آٹو فیس وغیرہ نہ بنے
                self.student.enrollments.filter(status='active').update(status='paused')
                
            term = "ممبر" if self.institution.type == 'masjid' else "طالب علم"
            return True, f"{term} کی صورتحال (Status) کامیابی سے اپ ڈیٹ کر دی گئی ہے۔", None
        return False, "کوئی طالب علم منتخب نہیں کیا گیا!", None

    @transaction.atomic
    def promote_student(self, new_course_id):
        """طالب علم کو ایک کلاس سے دوسری کلاس میں ترقی دینا اور پرانے کورس کو مکمل کرنا۔"""
        self._check_access()
        if not self.student: return False, "کوئی طالب علم منتخب نہیں کیا گیا!", None
        
        # 1. پرانے تمام جاری (Active) داخلوں کو مکمل مارک کریں
        Enrollment.objects.filter(
            student=self.student, 
            status=Enrollment.Status.ACTIVE
        ).update(status=Enrollment.Status.COMPLETED)
        
        # 2. نئے پروگرام میں داخلہ دیں (اگر پہلے سے موجود نہیں ہے)
        new_course = get_object_or_404(Course, pk=new_course_id, institution=self.institution)
        
        enrollment, created = Enrollment.objects.get_or_create(
            student=self.student,
            course=new_course,
            defaults={'status': Enrollment.Status.ACTIVE}
        )
        
        if not created:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save(update_fields=['status'])
            
        term = "ممبر" if self.institution.type == 'masjid' else "طالب علم"
        return True, f"{term} کو کامیابی سے '{new_course.title}' میں منتقل کر دیا گیا ہے۔", enrollment

    def get_student_detail_context(self, student_id):
        """طالب علم کے پروفائل صفحے کے لیے حاضری، فیس اور کورسز کا مکمل ڈیٹا۔"""
        student = get_object_or_404(Student, pk=student_id, institution=self.institution)
        self.set_student(student)
        self._check_access(student)
        
        finance_summary = self.finance().student_stats()
        attendance_summary = self.attendance().get_member_summary(student)
        member_metrics = self.attendance().get_member_metrics(student)
        
        from .institution import InstitutionManager
        return {
            "institution": self.institution,
            "student": student,
            "fees": self.finance().student_fee_history(),
            "attendance": attendance_summary,
            "enrollments": student.enrollments.all().select_related('course'),
            "wallet_balance": student.wallet_balance,
            "wallet_history": self.finance().student_wallet(),
            "currency_label": InstitutionManager.get_currency_label(self.institution),
            **finance_summary,
            **member_metrics
        }

    def get_self_dashboard_context(self):
        """خود طالب علم کے ذاتی ڈیش بورڈ کے لیے معلومات (ہوم ورک، فیس، حاضری)۔"""
        return {
            "student": self.student,
            "institution": self.institution,
            "recent_attendance": self.attendance().get_member_summary(self.student, limit=10),
            "pending_fees": self.finance().fee_dues(),
            "active_Courses": self.student.enrollments.filter(status='active').select_related('course')
        }

    def handle_detail_actions(self, request):
        """پروفائل کے صفحے سے ہونے والے مختلف کاموں (والٹ ٹاپ اپ، اسٹیٹس اپڈیٹ) کو مینیج کرنا۔"""
        action = request.POST.get("action")
        student_id = request.POST.get("student_id")
        target = get_object_or_404(Student, pk=student_id, institution=self.institution)
        self.set_student(target)
        
        if action == "add_to_wallet":
            return self.finance().pay(amount=request.POST.get("amount"), method="Cash", student_id=student_id)
        if action == "update_status":
            return self.update_status(request.POST.get("is_active") == "on")
        return False, "نامعلوم ایکشن کی درخواست کی گئی ہے۔", None
