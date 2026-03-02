import io
import zipfile
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.safestring import mark_safe
from safedelete.admin import SafeDeleteAdmin, highlight_deleted
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Sections:
   - Mixins (Security/Audit)
   - Institution Management
   - HR (Staff/Parents)
   - Academic (Students/Courses/Attendance)
   - Finance (Incomes/Expenses/Fees)
   - Backup & Exams
"""
from .resources import (
    InstitutionResource, CourseResource, FacilityResource,
    StudentResource, StaffResource, ParentResource, EnrollmentResource,
    ClassSessionResource, AttendanceResource, StaffAttendanceResource,
    AnnouncementResource, FeeResource, FeePaymentResource,
    DonorResource, IncomeResource, ExpenseResource, WalletTransactionResource,
    ExamResource, ExamResultResource
)


from ..models import (
    Attendance, ClassSession, Donor, Enrollment, Expense, Facility,
    Income, Institution, Parent, Course, Staff,
    Staff_Attendance, Student, Announcement, Fee, Fee_Payment, WalletTransaction,
    Exam, ExamResult, SystemSnapshot,
    ItemCategory, InventoryItem, AssetIssue, TimetableItem
)

# اگر exporting فائل موجود ہے تو امپورٹ، ورنہ اگنور
try:
    from ..exporting import (
        export_institution_to_csv_zip, export_institution_to_json, export_institutions_bundle, export_institution_to_excel
    )
except ImportError:
    export_institutions_bundle = None

User = get_user_model()

# ==========================================
# CUSTOM USER ADMIN (For DMS Linked Profiles)
# ==========================================
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from django.urls import reverse

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'get_linked_profiles')
    
    def get_linked_profiles(self, obj):
        profiles = []
        
        # Check Staff
        if hasattr(obj, 'staff'):
            prof = obj.staff
            inst = getattr(prof, 'institution', None)
            if inst:
                url = reverse('admin:dms_staff_change', args=[prof.id])
                text = prof.reg_id or f"{inst.reg_id or 'INS'}-E"
                profiles.append(f"<a href='{url}' style='color: #2563eb; text-decoration: none; font-weight: 500;'>👨‍💼 {text}</a>")
                
        # Check Student
        if hasattr(obj, 'student'):
            prof = obj.student
            inst = getattr(prof, 'institution', None)
            if inst:
                url = reverse('admin:dms_student_change', args=[prof.id])
                text = prof.reg_id or f"{inst.reg_id or 'INS'}-S"
                profiles.append(f"<a href='{url}' style='color: #16a34a; text-decoration: none; font-weight: 500;'>🎓 {text}</a>")
                
        # Check Parent
        if hasattr(obj, 'parent'):
            prof = obj.parent
            inst = getattr(prof, 'institution', None)
            if inst:
                url = reverse('admin:dms_parent_change', args=[prof.id])
                text = prof.reg_id or f"{inst.reg_id or 'INS'}-G"
                profiles.append(f"<a href='{url}' style='color: #d97706; text-decoration: none; font-weight: 500;'>👨‍👩‍👧 {text}</a>")
                
        # Check Admin (Owner)
        institutions_owned = getattr(obj, 'institution_set', None)
        if institutions_owned and institutions_owned.exists():
            for inst in institutions_owned.all():
                url = reverse('admin:dms_institution_change', args=[inst.id])
                text = f"{inst.reg_id or 'INS'}-A"
                profiles.append(f"<a href='{url}' style='color: #9333ea; text-decoration: none; font-weight: 500;'>👑 {text} (Owner)</a>")

        if not profiles:
            return format_html("<span style='color: #9ca3af;'>No Linked Profile</span>")
            
        return format_html("<br>".join(profiles))
        
    get_linked_profiles.short_description = "DMS Profiles & Roles"

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ایڈمن برانڈنگ
admin.site.site_header = "ڈی ایم ایس - ایڈمن"
admin.site.site_title = "ڈی ایم ایس ایڈمن"
admin.site.index_title = "انتظامی ڈیش بورڈ"


# --- Mixins ---
class RestrictedToInstitutionMixin(admin.ModelAdmin):
    institution_lookups = [
        "institution", "course__institution", "facility__institution",
        "student__institution", "staff_member__institution", "session__course__institution",
    ]

    def _user_institution(self, user):
        from ..logic.auth import UserManager
        if user.is_superuser: return None
        return UserManager.pick_primary_institution(user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        inst = self._user_institution(request.user)
        if not inst: return qs.none()
        
        # اگر یہ خود 'Institution' ماڈل ہے تو صرف اپنا ادارہ دکھائیں
        if qs.model == Institution:
            return qs.filter(pk=inst.pk)

        for lookup in self.institution_lookups:
            try:
                # سادہ چیک کہ کیا فیلڈ موجود ہے
                if lookup.split('__')[0] in [f.name for f in qs.model._meta.get_fields()]:
                    return qs.filter(**{lookup: inst})
            except: continue
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if "institution" in form.base_fields:
                form.base_fields.pop("institution")
        return form

class DeletedFilter(admin.SimpleListFilter):
    title = 'Recycle Bin'
    parameter_name = 'deleted_status'

    def lookups(self, request, model_admin):
        return (
            ('deleted', 'Deleted Only'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'deleted':
            return queryset.deleted_only()
        return queryset
class BaseAuditAdmin(ImportExportModelAdmin, SafeDeleteAdmin, SimpleHistoryAdmin, RestrictedToInstitutionMixin):
    """
    لائبریری بیسڈ ایڈمن جس میں ہسٹری، سافٹ ڈیلیٹ اور امپورٹ ایکسپورٹ شامل ہیں۔
    """
    list_display = (highlight_deleted, 'restore_link') + SafeDeleteAdmin.list_display
    list_filter = (DeletedFilter,)
    actions = ['restore_selected']

    class Media:
        css = {
            'all': ('css/admin.css',)
        }
    
    def get_list_display(self, request):
        base = super().get_list_display(request)
        # Ensure highlight_deleted and restore_link are at the start
        current = list(base)
        if 'restore_link' not in current:
            current.insert(current.index(highlight_deleted) + 1 if highlight_deleted in current else 0, 'restore_link')
        if highlight_deleted not in current:
            current.insert(0, highlight_deleted)
        return tuple(current)

    def restore_link(self, obj):
        if obj.deleted:
            from django.utils.html import format_html
            info = (self.model._meta.app_label, self.model._meta.model_name)
            url = reverse(f'admin:{info[0]}_{info[1]}_restore', args=[obj.pk])
            return format_html(
                '<a href="{}" style="color: #10b981; text-decoration: underline; font-weight: 500; font-size: 11px;">Restore</a>',
                url
            )
        return ""
    restore_link.short_description = "Restore"

    @admin.action(description="Restore selected items")
    def restore_selected(self, request, queryset):
        # We need to filter for only deleted items to avoid AssertionError
        count = 0
        for obj in queryset:
            # Check if object is actually deleted before restoring
            if hasattr(obj, 'undelete') and getattr(obj, 'deleted', None):
                obj.undelete()
                count += 1
        
        if count > 0:
            self.message_user(request, f"Successfully restored {count} records.", messages.SUCCESS)
        else:
            self.message_user(request, "No deleted records were selected to restore.", messages.WARNING)

    def get_urls(self):
        urls = super().get_urls()
        info = (self.model._meta.app_label, self.model._meta.model_name)
        custom_urls = [
            path('<path:object_id>/restore/', self.admin_site.admin_view(self.restore_view), name=f'{info[0]}_{info[1]}_restore'),
        ]
        return custom_urls + urls

    def restore_view(self, request, object_id):
        obj = self.model.objects.all_with_deleted().get(pk=object_id)
        if getattr(obj, 'deleted', None):
            obj.undelete()
            self.message_user(request, f"'{obj}' was successfully restored from Recycle Bin.", messages.SUCCESS)
        else:
            self.message_user(request, f"'{obj}' is already active.", messages.INFO)
        return redirect(reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_changelist'))

    def get_queryset(self, request):
        # We handle this via the DeletedFilter now
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        # 1. پہلے یوزر کا ادارہ حاصل کریں
        inst = self._user_institution(request.user)
        
        # 2. اگر ادارہ مل گیا ہے اور یہ ماڈل خود "Institution" نہیں ہے
        # تو سیو کرنے سے پہلے اس آبجیکٹ کے ساتھ ادارہ جوڑ دیں
        if inst and not isinstance(obj, Institution):
            obj.institution = inst
        
        # 3. اب سیو کریں (اب ایرر نہیں آئے گا کیونکہ ادارہ جڑ چکا ہے)
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        inst = self._user_institution(request.user)
        if inst and db_field.name == "institution":
            kwargs["queryset"] = Institution.objects.filter(pk=inst.pk)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class AutoUserCreationMixin:
    def _ensure_user(self, obj, prefix):
        from ..logic.auth import UserManager
        return UserManager.ensure_user(obj, prefix)

    def _notify_credentials(self, request, obj, password):
        from ..logic.auth import UserManager
        return UserManager.notify_credentials(request, obj, password)

# اردو ناموں کی اپڈیٹ
MAPPING_URDU = {
    Institution: ("ادارہ", "ادارے"), Donor: ("ڈونر", "ڈونرز"), Income: ("آمدنی", "آمدنی"),
    Expense: ("اخراجات", "اخراجات"), Staff: ("عملہ", "عملہ"), Parent: ("سرپرست", "سرپرست"),
    Staff_Attendance: ("عملہ روزانہ حاضری", "عملہ حاضری"), Student: ("طالب علم", "طلبہ"),
    Course: ("کورس", "کورسز"),
    Enrollment: ("داخلہ", "داخلے"), ClassSession: ("کلاس سیشن", "کلاس سیشنز"),
    Attendance: ("کلاس حاضری", "کلاس حاضری"), Facility: ("سہولت", "سہولیات"),
    Announcement: ("اعلان", "اعلانات"),
    Fee: ("طلبہ فیس", "طلبہ فیس"),
    WalletTransaction: ("والٹ ٹرانزیکشن", "والٹ ٹرانزیکشنز"),
    Exam: ("امتحان", "امتحانات"),
    ExamResult: ("امتحانی نتیجہ", "امتحانی نتائج"),
    SystemSnapshot: ("سسٹم اسنیپ شاٹ", "سسٹم اسنیپ شاٹس"),
}
for model, names in MAPPING_URDU.items():
    model._meta.verbose_name, model._meta.verbose_name_plural = names

# --- Admin Classes ---
class FeePaymentInline(admin.TabularInline):
    model = Fee_Payment
    extra = 0
    readonly_fields = ('payment_date', 'receipt_number')

@admin.register(Institution)
class InstitutionAdmin(BaseAuditAdmin):
    resource_class = InstitutionResource
    list_display = ("reg_id", "is_approved", "status", "user", "name", "slug", "address")
    list_filter = ("type", "is_approved", "status")
    search_fields = ("name", "user__username", "slug")
    
    ordering = ("name",)
    
    actions = ["download_complete_excel", "download_bundle_zip"]

    @admin.action(description="Download Master Ledger (Excel)")
    def download_complete_excel(self, request, queryset):
        if queryset.count() > 1:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for inst in queryset:
                    excel_bytes = export_institution_to_excel(inst)
                    archive.writestr(f"{inst.slug or inst.pk}.xlsx", excel_bytes)
            response = HttpResponse(buffer.getvalue(), content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="multiple_ledgers.zip"'
            return response
        else:
            inst = queryset.first()
            excel_bytes = export_institution_to_excel(inst)
            response = HttpResponse(excel_bytes, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{inst.slug}_ledger.xlsx"'
            return response

    @admin.action(description="Download Full Backup ZIP (All Data)")
    def download_bundle_zip(self, request, queryset):
        if export_institutions_bundle:
            zip_file = export_institutions_bundle(queryset, include_json=True, include_excel=True, include_csv=True)
            response = HttpResponse(zip_file, content_type="application/zip")
            response["Content-Disposition"] = 'attachment; filename="institutions_full_backup.zip"'
            return response
        else:
            self.message_user(request, "Exporting module not loaded.", level=messages.ERROR)


@admin.register(Staff)
class StaffAdmin(AutoUserCreationMixin, BaseAuditAdmin):
    resource_class = StaffResource
    list_display = ("full_name", "role", "institution", "is_active")
    list_filter = ("institution", "role")
    search_fields = ("name", "mobile")
    autocomplete_fields = ("institution", "user")
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(Student)
class StudentAdmin(AutoUserCreationMixin, BaseAuditAdmin):
    list_filter = ("institution", "is_active") # Filter hata diya (confusing tha)
    search_fields = ("name", "guardian_name", "mobile")
    autocomplete_fields = ("institution", "user")
    filter_horizontal = ("parents",)
    inlines = [FeePaymentInline]
    
    # actions = [...]  <-- یہ لائن ہٹا دی گئی ہے تاکہ پرانے ایکشنز ضائع نہ ہوں


    

    def get_form(self, request, obj=None, **kwargs):
        institution = self._user_institution(request.user)
        
        if obj is None:
            from .forms import StudentCreationForm
            
            class WrappedForm(StudentCreationForm):
                def __init__(self, *args, **kwargs):
                    kwargs['institution'] = institution
                    super().__init__(*args, **kwargs)
                    
                    # Inject Course Data for Auto-filling
                    import json
                    from django.utils.safestring import mark_safe
                    course_qs = self.fields['course'].queryset
                    data = {str(c.id): {'adm': str(c.admission_fee), 'crs': str(c.course_fee), 'label': c.get_fee_type_display(), 'type': c.fee_type} for c in course_qs}
                    
                    inline_js = f"""
                    <script>
                    (function() {{
                        const courseData = {json.dumps(data)};
                        function dmsUpdateStudentFees() {{
                            const courseId = document.querySelector('[name="course"]').value;
                            const info = courseData[courseId];
                            const feeType = document.querySelector('[name="custom_fee_type"]').value;

                            function safeSet(name, val) {{
                                const el = document.querySelector(`[name="${{name}}"]`);
                                if (el && document.activeElement !== el) el.value = val;
                            }}

                            if (info) {{
                                if (feeType === 'free') {{
                                    safeSet('agreed_admission_fee', "0.00");
                                    safeSet('agreed_course_fee', "0.00");
                                    safeSet('admission_discount', info.adm);
                                    safeSet('course_discount', info.crs);
                                }} else {{
                                    safeSet('agreed_admission_fee', info.adm);
                                    safeSet('agreed_course_fee', info.crs);
                                    safeSet('custom_fee_type', feeType || info.type || "");
                                    safeSet('admission_discount', "0");
                                    safeSet('course_discount', "0");
                                }}
                            }}
                        }}
                        // Event Listeners
                        document.addEventListener('change', (e) => {{
                            if (e.target.name === 'course' || e.target.name === 'custom_fee_type') dmsUpdateStudentFees();
                        }});
                        // Select2 and Initial Load
                        window.addEventListener('load', () => {{
                            if (window.jQuery) jQuery('[name="course"]').on('change select2:select', dmsUpdateStudentFees);
                            dmsUpdateStudentFees();
                        }});
                        // zero-clearing logic
                        document.addEventListener('focusin', (e) => {{
                            if (['admission_discount', 'course_discount', 'agreed_admission_fee', 'agreed_course_fee'].includes(e.target.name)) {{
                                if (e.target.value === '0' || e.target.value === '0.00' || e.target.value === '0.0') e.target.value = '';
                            }}
                        }});
                        document.addEventListener('focusout', (e) => {{
                            if (['admission_discount', 'course_discount', 'agreed_admission_fee', 'agreed_course_fee'].includes(e.target.name)) {{
                                if (e.target.value === '') e.target.value = '0';
                            }}
                        }});
                        // Fail-safe
                        setInterval(() => {{
                            const agreed = document.querySelector('[name="agreed_course_fee"]');
                            if (agreed && !agreed.value && document.querySelector('[name="course"]').value) dmsUpdateStudentFees();
                        }}, 2000);
                    }})();
                    </script>
                    """
                    self.fields['course'].help_text = mark_safe(inline_js + (self.fields['course'].help_text or ""))
            
            kwargs['form'] = WrappedForm
            
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change and 'course' in form.cleaned_data:
            course = form.cleaned_data.get('course')
            if course:
                if not Enrollment.objects.filter(student=obj, course=course, status=Enrollment.Status.ACTIVE).exists():
                    Enrollment.objects.create(
                        student=obj,
                        course=course,
                        agreed_admission_fee=form.cleaned_data.get('agreed_admission_fee') or 0,
                        admission_fee_discount=form.cleaned_data.get('admission_discount') or 0,
                        agreed_course_fee=form.cleaned_data.get('agreed_course_fee') or 0,
                        course_fee_discount=form.cleaned_data.get('course_discount') or 0,
                        fee_start_month=form.cleaned_data.get('fee_start_month') or timezone.now().date(),
                        fee_type_override=form.cleaned_data.get('custom_fee_type'),
                        status=Enrollment.Status.ACTIVE
                    )
                    messages.success(request, f"Student enrolled in '{course.title}' with defined fees.")

@admin.register(Parent)
class ParentAdmin(AutoUserCreationMixin, BaseAuditAdmin):
    resource_class = ParentResource
    list_display = ("full_name", "relationship", "institution")
    search_fields = ("name", "mobile")
    autocomplete_fields = ("institution", "user")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

@admin.register(Course)
class CourseAdmin(BaseAuditAdmin):
    resource_class = CourseResource
    list_display = ("title", "category", "institution", "capacity", "is_active")
    list_filter = ("institution", "category", "is_active")
    search_fields = ("title",)  
    autocomplete_fields = ("institution",)

from django import forms
class EnrollmentAdminForm(forms.ModelForm):
    actual_adm = forms.CharField(label="اصل داخلہ فیس (کورس کی)", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly', 'style': 'background-color: #eee; font-weight: bold; border: 1px solid #ccc;'}))
    actual_crs = forms.CharField(label="اصل ماہانہ فیس (کورس کی)", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly', 'style': 'background-color: #eee; font-weight: bold; border: 1px solid #ccc;'}))
    actual_type = forms.CharField(label="فیس کی قسم", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly', 'style': 'background-color: #eee; font-weight: bold; border: 1px solid #ccc;'}))

    adm_discount_type = forms.ChoiceField(choices=[('fixed', 'رقم'), ('percent', 'فیصد ')], label="رعایت کی قسم (داخلہ)", initial='fixed')
    adm_discount_value = forms.DecimalField(label="رعایت کی ویلیو", initial=0, required=False)
    crs_discount_type = forms.ChoiceField(choices=[('fixed', 'رقم'), ('percent', 'فیصد ')], label="رعایت کی قسم (کورس)", initial='fixed')
    crs_discount_value = forms.DecimalField(label="رعایت کی ویلیو", initial=0, required=False)
    
    fee_type_override = forms.ChoiceField(
        choices=[('', 'کورس کے مطابق')] + Enrollment.FEE_TYPE_CHOICES, 
        label="فیس کی قسم / طریقہ کار (Override)", 
        required=False
    )

    update_current_fee = forms.BooleanField(
        label="موجودہ مہینے کی فیس بھی اپڈیٹ کریں؟",
        required=False, initial=False,
        help_text="اگر ٹک کیا تو پینڈنگ فیس نئی رقم پر سیٹ ہو جائے گی۔"
    )

    class Meta:
        model = Enrollment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initial values for edit mode
        if self.instance and self.instance.pk:
            self.fields['adm_discount_value'].initial = self.instance.admission_fee_discount
            self.fields['crs_discount_value'].initial = self.instance.course_fee_discount
            self.fields['fee_type_override'].initial = self.instance.fee_type_override or ''
            
            if self.instance.course:
                self.fields['actual_adm'].initial = self.instance.course.admission_fee
                self.fields['actual_crs'].initial = self.instance.course.course_fee
                self.fields['actual_type'].initial = self.instance.course.get_fee_type_display()

        # SUPER ROBUST INLINE JS + BIDIRECTIONAL CALCULATOR
        import json
        from django.utils.safestring import mark_safe
        course_qs = self.fields['course'].queryset
        data = {str(c.id): {'adm': str(c.admission_fee), 'crs': str(c.course_fee), 'label': c.get_fee_type_display(), 'type': c.fee_type} for c in course_qs}
        
        inline_js = f"""
        <script>
        (function() {{
            const courseData = {json.dumps(data)};
            
            function safeSet(name, val) {{
                const el = document.querySelector(`[name="${{name}}"]`);
                if (el && document.activeElement !== el) el.value = val;
            }}

            // 1. Calculate Agreed Fee from Discount
            function calcAgreed(prefix) {{
                const actual = parseFloat(document.querySelector(`[name="actual_${{prefix}}"]`).value) || 0;
                const discVal = parseFloat(document.querySelector(`[name="${{prefix}}_discount_value"]`).value) || 0;
                const discType = document.querySelector(`[name="${{prefix}}_discount_type"]`).value;
                const tName = prefix === 'adm' ? 'agreed_admission_fee' : 'agreed_course_fee';
                
                let final = actual;
                if (discType === 'percent') final = actual - (actual * discVal / 100);
                else final = actual - discVal;
                safeSet(tName, Math.max(0, final).toFixed(2));
            }}

            // 2. Calculate Discount from Agreed Fee (Manual entry)
            function calcDiscount(prefix) {{
                const actual = parseFloat(document.querySelector(`[name="actual_${{prefix}}"]`).value) || 0;
                const agreed = parseFloat(document.querySelector(`[name="agreed_${{prefix === 'adm' ? 'admission' : 'course'}}_fee"]`).value) || 0;
                const discType = document.querySelector(`[name="${{prefix}}_discount_type"]`).value;
                const tName = `${{prefix}}_discount_value`;
                
                let diff = actual - agreed;
                let finalVal = "0";
                if (discType === 'percent' && actual > 0) finalVal = ((diff / actual) * 100).toFixed(2);
                else finalVal = diff.toFixed(2);
                safeSet(tName, finalVal);
            }}

            function dmsUpdateFees() {{
                const courseId = document.querySelector('[name="course"]').value;
                const info = courseData[courseId];
                const overrideType = document.querySelector('[name="fee_type_override"]').value;

                if (info) {{
                    safeSet('actual_adm', info.adm);
                    safeSet('actual_crs', info.crs);
                    safeSet('actual_type', info.label);
                    
                    if (overrideType === 'free') {{
                        safeSet('agreed_admission_fee', "0.00");
                        safeSet('agreed_course_fee', "0.00");
                        safeSet('adm_discount_value', info.adm);
                        safeSet('crs_discount_value', info.crs);
                        safeSet('adm_discount_type', 'fixed');
                        safeSet('crs_discount_type', 'fixed');
                    }} else {{
                        safeSet('fee_type_override', overrideType || info.type || "");
                        calcAgreed('adm');
                        calcAgreed('crs');
                    }}
                }}
            }}

            document.addEventListener('input', (e) => {{
                if (e.target.name === 'adm_discount_value') calcAgreed('adm');
                if (e.target.name === 'crs_discount_value') calcAgreed('crs');
                if (e.target.name === 'agreed_admission_fee') calcDiscount('adm');
                if (e.target.name === 'agreed_course_fee') calcDiscount('crs');
            }});
            
            document.addEventListener('change', (e) => {{
                if (e.target.name === 'course' || e.target.name === 'fee_type_override') dmsUpdateFees();
                if (e.target.name === 'adm_discount_type') calcAgreed('adm');
                if (e.target.name === 'crs_discount_type') calcAgreed('crs');
            }});

            window.addEventListener('load', () => {{
                if (window.jQuery) jQuery('[name="course"]').on('change select2:select', dmsUpdateFees);
                dmsUpdateFees();
            }});

            // zero-clearing logic
            document.addEventListener('focusin', (e) => {{
                if (['adm_discount_value', 'crs_discount_value', 'agreed_admission_fee', 'agreed_course_fee'].includes(e.target.name)) {{
                    if (e.target.value === '0' || e.target.value === '0.00' || e.target.value === '0.0') e.target.value = '';
                }}
            }});
            document.addEventListener('focusout', (e) => {{
                if (['adm_discount_value', 'crs_discount_value', 'agreed_admission_fee', 'agreed_course_fee'].includes(e.target.name)) {{
                    if (e.target.value === '') e.target.value = '0';
                }}
            }});

            setInterval(() => {{
                if (!document.querySelector('[name="actual_adm"]').value && document.querySelector('[name="course"]').value) dmsUpdateFees();
            }}, 2500);
        }})();
        </script>
        """
        self.fields['course'].help_text = mark_safe(inline_js + (self.fields['course'].help_text or ""))

    def save(self, commit=True):
        instance = super().save(commit=False)
        # We manually map the form's calculated discounts to the model
        adm_val = self.cleaned_data.get('adm_discount_value') or 0
        if self.cleaned_data.get('adm_discount_type') == 'percent' and instance.course:
            instance.admission_fee_discount = (instance.course.admission_fee * adm_val) / 100
        else:
            instance.admission_fee_discount = adm_val
            
        crs_val = self.cleaned_data.get('crs_discount_value') or 0
        if self.cleaned_data.get('crs_discount_type') == 'percent' and instance.course:
            instance.course_fee_discount = (instance.course.course_fee * crs_val) / 100
        else:
            instance.course_fee_discount = crs_val
            
        instance.fee_type_override = self.cleaned_data.get('fee_type_override') or None
        
        if commit:
            instance.save()
        return instance

@admin.register(Enrollment)
class EnrollmentAdmin(BaseAuditAdmin):
    resource_class = EnrollmentResource
    form = EnrollmentAdminForm
    list_display = ("student", "student__reg_id", "course", "status", "agreed_course_fee")
    search_fields = ("student__reg_id", "student__name")
    list_filter = ("status", "course__institution")
    autocomplete_fields = ("student",)
    readonly_fields = ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get('update_current_fee'):
            from dms.models import Fee
            from django.contrib import messages
            from django.db.models import Case, When, F, Value
            
            # Non-paid statuses
            unpaid = [Fee.Status.PENDING, Fee.Status.OVERDUE, Fee.Status.PARTIAL]
            
            # Logic: 
            # 1. If Paid > Agreed Fee (e.g. Free case where 0 < 500), set Due = Paid (Balance 0).
            # 2. If Paid <= Agreed Fee (e.g. Hiking fee 500 < 2000), set Due = Agreed (Balance 1500).
            # 3. Status: If Agreed is 0 and nothing Paid -> WAIVED. Else keep status.

            # 1. Update Course Fees
            course_updates = {
                'amount_due': Case(
                    When(amount_paid__gt=obj.agreed_course_fee, then=F('amount_paid')),
                    default=Value(obj.agreed_course_fee)
                ),
                'discount': 0, 'late_fee': 0
            }
            if obj.agreed_course_fee == 0:
                course_updates['status'] = Case(
                    When(amount_paid__gt=0, then=F('status')),
                    default=Value(Fee.Status.WAIVED)
                )

            Fee.objects.filter(
                enrollment=obj, 
                status__in=unpaid, 
                fee_type__in=['monthly', 'fixed', 'installment']
            ).update(**course_updates)
            
            # 2. Update Admission Fees
            adm_updates = {
                'amount_due': Case(
                    When(amount_paid__gt=obj.agreed_admission_fee, then=F('amount_paid')),
                    default=Value(obj.agreed_admission_fee)
                ),
                'discount': 0, 'late_fee': 0
            }
            if obj.agreed_admission_fee == 0:
                adm_updates['status'] = Case(
                    When(amount_paid__gt=0, then=F('status')),
                    default=Value(Fee.Status.WAIVED)
                )

            Fee.objects.filter(
                enrollment=obj, 
                status__in=unpaid, 
                fee_type='admission'
            ).update(**adm_updates)
            
            messages.success(request, "موجودہ غیر ادا شدہ فیسیں (Bills) کامیابی سے اپڈیٹ کر دی گئیں۔")

    fieldsets = (
        (None, {'fields': (('student', 'course'), ('enrollment_date', 'status'))}),
        ('فیس اور رعایت (داخلہ)', {'fields': ('actual_adm', ('adm_discount_type', 'adm_discount_value'), 'agreed_admission_fee')}),
        ('فیس اور رعایت (کورس)', {'fields': ('actual_crs', 'actual_type', ('crs_discount_type', 'crs_discount_value'), 'agreed_course_fee')}),
        ('دیگر', {'fields': ('fee_type_override', 'fee_start_month', 'update_current_fee')}),
    )

@admin.register(ClassSession)
class ClassSessionAdmin(BaseAuditAdmin):
    resource_class = ClassSessionResource
    list_display = ("course", "date", "session_type")
    list_filter = ("course__institution", "date")
    search_fields = ("topic", "course__title") 
    autocomplete_fields = ("course",)  

@admin.register(Attendance)
class AttendanceAdmin(BaseAuditAdmin):
    resource_class = AttendanceResource
    list_display = ("session", "student", "status")
    list_filter = ("status", "session__course__institution")
    autocomplete_fields = ("session", "student")

@admin.register(Facility)
class FacilityAdmin(BaseAuditAdmin):
    resource_class = FacilityResource
    list_display = ("name", "facility_type", "is_available")
    list_filter = ("institution", "facility_type")
    search_fields = ("name",) 
    autocomplete_fields = ("institution",)


@admin.register(Income)
class IncomeAdmin(BaseAuditAdmin):
    resource_class = IncomeResource
    list_display = ("receipt_number", "amount", "source", "date", "institution")
    list_filter = ("institution", "source")
    search_fields = ("receipt_number", "description")
    autocomplete_fields = ("institution", "donor")

@admin.register(Expense)
class ExpenseAdmin(BaseAuditAdmin):
    resource_class = ExpenseResource
    list_display = ("receipt_number", "amount", "category", "date", "institution")
    list_filter = ("institution", "category")
    search_fields = ("receipt_number", "description")
    autocomplete_fields = ("institution",)


@admin.register(Fee)
class FeeAdmin(BaseAuditAdmin):
    resource_class = FeeResource
    list_display = ("title", "student", "amount_due", "amount_paid", "status")
    list_filter = ("institution", "status")
    autocomplete_fields = ("institution", "student")
    inlines = [FeePaymentInline]

@admin.register(Fee_Payment)
class FeePaymentAdmin(BaseAuditAdmin):
    resource_class = FeePaymentResource
    list_display = ("receipt_number", "fee", "amount", "payment_method", "payment_date")
    list_filter = ("payment_method", "payment_date")
    search_fields = ("receipt_number", "fee__student__name")
    readonly_fields = ("receipt_number", "payment_date")
    
    def get_queryset(self, request):
        from django.db.models import Q
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        inst = self._user_institution(request.user)
        if not inst: return qs.none()
        # Look for institution via fee OR student
        return qs.filter(Q(fee__institution=inst) | Q(student__institution=inst)).distinct()

@admin.register(Donor)
class DonorAdmin(BaseAuditAdmin):
    resource_class = DonorResource
    list_display = ("name", "institution", "phone")
    search_fields = ("name",)

@admin.register(Announcement)
class AnnouncementAdmin(BaseAuditAdmin):
    resource_class = AnnouncementResource
    list_display = ("title", "institution", "is_published")
    filter_horizontal = ("target_parents",)
    autocomplete_fields = ("institution",)

@admin.register(Staff_Attendance)
class Staff_AttendanceAdmin(BaseAuditAdmin):
    resource_class = StaffAttendanceResource
    list_display = ("date", "staff_member", "status")
    list_filter = ("institution", "status", "date")
    autocomplete_fields = ("institution", "staff_member")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(BaseAuditAdmin):
    resource_class = WalletTransactionResource
    list_display = ("student", "transaction_type", "amount", "date")
    list_filter = ("transaction_type", "date")
    search_fields = ("student__name", "description")
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        inst = self._user_institution(request.user)
        if not inst: return qs.none()
        return qs.filter(student__institution=inst)


@admin.register(Exam)
class ExamAdmin(BaseAuditAdmin):
    resource_class = ExamResource
    list_display = ("title", "term", "start_date", "end_date", "institution")
    list_filter = ("term", "institution", "is_active")
    search_fields = ("title",)

@admin.register(ExamResult)
class ExamResultAdmin(BaseAuditAdmin):
    resource_class = ExamResultResource
    list_display = ("student", "exam", "obtained_marks", "total_marks", "grade")
    list_filter = ("exam", "exam__institution")
    search_fields = ("student__name", "exam__title")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        inst = self._user_institution(request.user)
        if not inst: return qs.none()
        return qs.filter(exam__institution=inst)

@admin.register(SystemSnapshot)
class SystemSnapshotAdmin(admin.ModelAdmin):
    list_display = ("label", "institution_name", "backup_type", "size_kb", "created_at")
    list_filter = ("backup_type", "created_at", "institution")
    search_fields = ("label", "notes")
    readonly_fields = ("file", "size", "created_at")
    
    def institution_name(self, obj):
        return obj.institution.name if obj.institution else "پورے سسٹم"
    institution_name.short_description = "ادارہ"

    def size_kb(self, obj):
        return f"{obj.size / 1024:.2f} KB"
    size_kb.short_description = "سائز"

    def has_add_permission(self, request):
        return False # صرف کمانڈ یا ڈیش بورڈ سے بنے گا

    # ایکشنز (Actions)
    actions = ["restore_snapshot"]

    @admin.action(description="منتخب بیک اپ ری اسٹور کریں")
    def restore_snapshot(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "براہ کرم ایک وقت میں صرف ایک ہی اسنیپ شاٹ منتخب کریں۔", level=messages.ERROR)
            return

        snapshot = queryset.first()
        try:
            from .exporting import import_institution_from_json
            import zipfile
            
            with snapshot.file.open('rb') as f:
                with zipfile.ZipFile(f) as z:
                    json_file = next((f for f in z.namelist() if f.endswith(".json")), None)
                    if not json_file:
                        raise Exception("درست ڈیٹا فائل نہیں ملی۔")
                    
                    json_content = z.read(json_file).decode('utf-8')
                    
                    if snapshot.institution:
                        results = import_institution_from_json(snapshot.institution, json_content)
                        if "error" in results:
                             raise Exception(results["error"])
                        self.message_user(request, f"ادارہ '{snapshot.institution.name}' کامیابی سے ری اسٹور ہو گیا!")
                    else:
                        # سسٹم ری اسٹور لاجک
                        from ..exporting import import_institution_from_json
                        institutions_restored = 0
                        json_files = [f for f in z.namelist() if f.endswith(".json")]
                        
                        for json_path in json_files:
                            slug_candidate = json_path.split('/')[0]
                            try:
                                institution = Institution.objects.get(slug=slug_candidate)
                                j_content = z.read(json_path).decode('utf-8')
                                import_institution_from_json(institution, j_content)
                                institutions_restored += 1
                            except Institution.DoesNotExist:
                                pass
                        self.message_user(request, f"سسٹم کامیابی سے ری اسٹور ہو گیا! ({institutions_restored} ادارے)")

        except Exception as e:
            self.message_user(request, f"ری اسٹور میں غلطی: {str(e)}", level=messages.ERROR)


@admin.register(ItemCategory)
class ItemCategoryAdmin(BaseAuditAdmin):
    list_display = ("name", "institution")
    search_fields = ("name",)

@admin.register(InventoryItem)
class InventoryItemAdmin(BaseAuditAdmin):
    list_display = ("name", "item_type", "total_quantity", "available_quantity", "institution")
    list_filter = ("item_type", "institution")
    search_fields = ("name",)

@admin.register(AssetIssue)
class AssetIssueAdmin(BaseAuditAdmin):
    list_display = ("item", "get_receiver", "issue_date", "due_date", "is_returned")
    list_filter = ("is_returned", "issue_date")
    
    def get_receiver(self, obj):
        return obj.student.full_name if obj.student else obj.staff.full_name if obj.staff else "نامعلوم"
    get_receiver.short_description = "وصول کنندہ"

@admin.register(TimetableItem)
class TimetableItemAdmin(BaseAuditAdmin):
    list_display = ("day_of_week", "start_time", "course", "teacher", "subject")
    list_filter = ("day_of_week", "course__institution", "teacher")
    search_fields = ("subject", "course__title")
