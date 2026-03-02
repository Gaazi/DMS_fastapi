from django import forms
from ..models import (
    ClassSession,
    Donor,
    Enrollment,
    Expense,
    Facility,
    Income,
    Course,
    Staff,
    Student,
    Parent,
    Fee,
)

class DonorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tactical styling
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label

    class Meta:
        model = Donor
        fields = ["name", "phone", "email", "address"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Forms:
   - IncomeForm/ExpenseForm (Line 31) - Finance recording
   - StaffForm/StudentForm (Line 54) - HR and Academic profiles
   - CourseForm/EnrollmentForm (Line 90) - Course management
   - ClassSessionForm (Line 122) - Attendance marking
   - AttendanceReportForm (Line 144) - Date range reports
   - StudentFeeForm (Line 172) - Manual fee adjustments
"""

class IncomeForm(forms.ModelForm):
    # ... (No changes usually, but context lines required for match)
    new_donor_name = forms.CharField(required=False, label="نیا ڈونر کا نام")
    new_donor_phone = forms.CharField(required=False, label="فون نمبر")
    new_donor_email = forms.EmailField(required=False, label="ای میل")
    new_donor_address = forms.CharField(required=False, label="پتہ", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tactical styling (Removed) - Only placeholders
        for field_name, field in self.fields.items():
            field.widget.attrs['placeholder'] = field.label

        donor_field = self.fields.get("donor")
        if donor_field:
            donor_field.empty_label = "ڈونر سلیکٹ کریں / یا گمنام عطیہ درج کریں"
            if institution is None:
                donor_field.queryset = Donor.objects.none()
            else:
                donor_field.queryset = institution.donors.all()
            donor_field.required = False
            
            # Add Alpine.js hook
            donor_field.widget.attrs.update({
                'x-model': 'selectedDonor',
            })

        source_field = self.fields.get("source")
        if source_field:
            source_field.label = "عطیہ کی مد سلیکٹ کریں"
            source_field.initial = ""  # بائی ڈیفالٹ خالی رکھیں
            source_field.choices = [("", "عطیہ کی مد سلیکٹ کریں")] + list(source_field.choices)

    class Meta:
        model = Income
        fields = [
            "donor", "new_donor_name", "new_donor_phone", "new_donor_email", 
            "new_donor_address", "source", "amount", "description"
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class PublicSupportForm(forms.Form):
    donor_name = forms.CharField(label="آپ کا نام", max_length=100)
    donor_phone = forms.CharField(label="فون نمبر", max_length=15, required=False)
    amount = forms.DecimalField(label="رقم", min_value=1)
    description = forms.CharField(label="پیغام (اختیاری)", widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = "glass-input font-sans"

class ExpenseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tactical styling (Removed) - Only placeholders
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label

    class Meta:
        model = Expense
        fields = ["category", "amount", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class StaffForm(forms.ModelForm):
    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Standard styling (Fixed Height for Alignment)
        base_classes = "w-full h-10 bg-transparent text-gray-900 border border-gray-300 rounded-lg px-3 text-sm focus:border-emerald-500 focus:ring-emerald-500 placeholder:text-gray-400"
        checkbox_classes = "w-5 h-5 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500"
        
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': checkbox_classes})
            else:
                field.widget.attrs.update({'class': base_classes, 'placeholder': field.label, 'style': 'color-scheme: light;'})
            
        # Specific overrides for Salary (LTR)
        if 'base_salary' in self.fields:
             existing_class = self.fields['base_salary'].widget.attrs.get('class', '')
             self.fields['base_salary'].widget.attrs.update({
                 'class': f"{existing_class} text-left font-mono",
                 'dir': 'ltr'
             })

        # Set sensible defaults for new staff
        if not self.instance.pk:
            from django.utils import timezone
            self.fields['hire_date'].initial = timezone.now().date()
            self.fields['shift_start'].initial = "08:00"
            self.fields['shift_end'].initial = "14:00"
            if 'base_salary' in self.fields:
                self.fields['base_salary'].initial = None

        # --- Role Filtering based on Institution Type ---
        if institution and hasattr(institution, 'type') and 'role' in self.fields:
            from ..logic.roles import Role
            if institution.type == 'masjid':
                # مسجد میں مہتمم اور استاد نہیں ہوتے (عام طور پر)
                excluded_roles = [Role.ACADEMIC_HEAD, Role.TEACHER]
                self.fields['role'].choices = [c for c in Role.choices if c[0] not in excluded_roles]
            elif institution.type in ['madrasa', 'maktab']:
                # مدرسہ/مکتب میں امام اور موذن نہیں ہوتے (جب تک مسجد ساتھ نہ ہو)
                excluded_roles = [Role.IMAM, Role.MUEZZIN]
                self.fields['role'].choices = [c for c in Role.choices if c[0] not in excluded_roles]

    class Meta:
        model = Staff
        fields = [
            "name", "role", "base_salary", "photo", "mobile", "email", 
            "address", "hire_date", "shift_start", "shift_end", "is_active", "notes"
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "shift_start": forms.TimeInput(attrs={"type": "time"}),
            "shift_end": forms.TimeInput(attrs={"type": "time"}),
        }


class StudentForm(forms.ModelForm):
    """
    Base Form for Student Profile (Used for Edit Mode)
    """
    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Tactical styling for all fields
        for name, field in self.fields.items():
            field.widget.attrs.update({'placeholder': field.label})
        
        # Make fields optional if they are not strictly required for a basic profile
        # Make fields optional if they are not strictly required for a basic profile
        if 'enrollment_date' in self.fields: self.fields['enrollment_date'].required = False

    class Meta:
        model = Student
        fields = [
            "name", "father_name", "gender", "blood_group", "photo", 
            "guardian_name", "guardian_relation",  "mobile", "mobile2",
            "email", "address", "enrollment_date", "date_of_birth", "is_active", "notes"
        ]
        widgets = {
            "guardian_relation": forms.Select(choices=Parent.Relation.choices),
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "enrollment_date": forms.DateInput(attrs={"type": "date"}),
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }



class StudentCreationForm(StudentForm):
    course = forms.ModelChoiceField(queryset=Course.objects.none(), label="کورس", empty_label="انتخاب کریں")
    actual_adm = forms.DecimalField(label="داخلہ فیس", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    adm_discount_type = forms.ChoiceField(choices=[('fixed', 'رقم'), ('percent', 'فیصد')], label="رعایت کی قسم", initial='fixed')
    admission_discount = forms.DecimalField(required=False, label="داخلہ رعایت", initial=0)
    agreed_admission_fee = forms.DecimalField(required=False, label="طے شدہ داخلہ فیس")
    
    actual_crs = forms.DecimalField(label="کورس فیس", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    actual_type_label = forms.CharField(label="قسم", required=False, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    crs_discount_type = forms.ChoiceField(choices=[('fixed', 'رقم'), ('percent', 'فیصد')], label="رعایت کی قسم", initial='fixed')
    course_discount = forms.DecimalField(required=False, label="ماہانہ رعایت", initial=0)
    agreed_course_fee = forms.DecimalField(required=False, label="طے شدہ ماہانہ فیس")
    
    fee_start_month = forms.DateField(required=False, label="فیس آغاز", widget=forms.DateInput(attrs={"type": "date"}))
    custom_fee_type = forms.ChoiceField(choices=Course.FeeType.choices, required=False, label="Fee Type")
    initial_payment = forms.DecimalField(required=False, label="ادائیگی کی رقم", min_value=0, initial=0)
    payment_method = forms.ChoiceField(choices=[('Cash', 'نقد'), ('Online', 'آن لائن'), ('Bank', 'بینک')], initial='Cash', label="Payment Method")

    class Meta(StudentForm.Meta):
        fields = [
            "name", "father_name", "gender", "blood_group",  
            "guardian_name", "guardian_relation", "mobile", "mobile2",
            "email", "address", "enrollment_date", "date_of_birth", "notes",
            'course', 'actual_adm', 'adm_discount_type', 'admission_discount', 'agreed_admission_fee',
            'actual_crs', 'actual_type_label', 'crs_discount_type', 'course_discount', 'agreed_course_fee',
            'fee_start_month', 'custom_fee_type', 'initial_payment', 'payment_method'
        ]

    def __init__(self, *args, institution=None, **kwargs):
        course_obj = kwargs.pop('course_obj', None)
        super().__init__(*args, institution=institution, **kwargs)
        
        if institution:
            self.fields['course'].queryset = Course.objects.filter(institution=institution, is_active=True)
            # We make course optional for everyone now, so students can be registered and linked later
            self.fields['course'].required = False
            
            # Mosques might not enforce courses/programs for simple Musalleen
            if hasattr(institution, 'type') and institution.type == 'masjid':
                 self.fields['course'].label = "پروگرام / کیمپین"
                 self.fields['course'].empty_label = "پروگرام یا کیٹیگری منتخب کریں"
                 self.fields['actual_adm'].label = "ممبر فیس"
                 self.fields['admission_discount'].label = "ممبر رعایت"
                 self.fields['agreed_admission_fee'].label = "طے شدہ ممبر فیس"
                 self.fields['actual_crs'].label = "ماہانہ ممبرشپ"
                 self.fields['course_discount'].label = "ماہانہ رعایت"
                 self.fields['agreed_course_fee'].label = "طے شدہ ماہانہ ممبرشپ"
                 
                 # Update placeholders to match new labels
                 for field_name in ['actual_adm', 'admission_discount', 'agreed_admission_fee', 'actual_crs', 'course_discount', 'agreed_course_fee']:
                     self.fields[field_name].widget.attrs['placeholder'] = self.fields[field_name].label
            
        # طالب علم کے نام کے لیے تجاویز (Suggestions) کی لسٹ جوڑنا
        self.fields['name'].widget.attrs.update({
            'list': 'student-list',
            'autocomplete': 'off'
        })

        # --- Auto-Load Active Enrollment Data (Edit Mode) ---
        if self.instance and self.instance.pk:
            active_enrollment = self.instance.enrollments.filter(status='active').first()
            if active_enrollment:
                # Pre-fill enrollment-specific fields
                self.initial['course'] = active_enrollment.course_id
                self.initial['agreed_admission_fee'] = active_enrollment.agreed_admission_fee
                self.initial['admission_discount'] = active_enrollment.admission_fee_discount
                self.initial['agreed_course_fee'] = active_enrollment.agreed_course_fee
                self.initial['course_discount'] = active_enrollment.course_fee_discount
                self.initial['fee_start_month'] = active_enrollment.fee_start_month
                self.initial['custom_fee_type'] = active_enrollment.fee_type_override
                
                # Also set the course_obj internally so logic below works for display fields
                course_obj = active_enrollment.course
        
        if course_obj:
            self.fields['course'].initial = course_obj.id
            from decimal import Decimal
            actual_adm = course_obj.admission_fee or Decimal('0')
            actual_crs = course_obj.course_fee or Decimal('0')
            
            self.fields['actual_adm'].initial = actual_adm
            self.fields['actual_crs'].initial = actual_crs
            self.fields['actual_type_label'].initial = course_obj.get_fee_type_display()
            self.fields['custom_fee_type'].initial = course_obj.fee_type
            
            # رعایت (Discount) کو مدنظر رکھتے ہوئے ملے جلے حساب کتاب کا آغاز
            adm_disc = (self['admission_discount'].initial or Decimal('0')) if 'admission_discount' in self.fields else Decimal('0')
            crs_disc = (self['course_discount'].initial or Decimal('0')) if 'course_discount' in self.fields else Decimal('0')

            self.fields['agreed_admission_fee'].initial = max(Decimal('0'), actual_adm - adm_disc)
            self.fields['agreed_course_fee'].initial = max(Decimal('0'), actual_crs - crs_disc)
            

            if course_obj.fee_type == 'free':
                self.fields['agreed_admission_fee'].initial = 0
                self.fields['agreed_course_fee'].initial = 0

    def clean_fee_start_month(self):
        fee_start_month = self.cleaned_data.get('fee_start_month')
        if not fee_start_month:
            from django.utils import timezone
            return timezone.now().date()
        return fee_start_month




class PublicAdmissionForm(StudentForm):
    """
    [PUBLIC] Admission Form (Simple & Safe)
    """
    course = forms.ModelChoiceField(queryset=Course.objects.none(), label="داخلہ مطلوبہ کورس", empty_label="کورس منتخب کریں")

    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, institution=institution, **kwargs)
        if institution:
            self.fields['course'].queryset = Course.objects.filter(institution=institution, is_active=True)
    
    class Meta(StudentForm.Meta):
        # Exclude internal fields
        fields = [
            "name", "father_name", "gender", "date_of_birth", "blood_group", "photo",
            "guardian_name", "guardian_relation", "mobile", "mobile2",
            "email", "address"
        ]


class CourseForm(forms.ModelForm):
    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Institution Type Logic for Categories
        if institution:
             # from ..models.foundation_model import Institution  <-- Model already imported via ..models
             # Check for instructors
             if 'instructors' in self.fields:
                 self.fields['instructors'].queryset = Staff.objects.filter(
                    institution=institution, 
                    is_active=True
                 ).order_by('name')

             # Check if institution type is MAKTAB
             if hasattr(institution, 'type') and institution.type == 'maktab':
                 # Defined allowed choices for Maktab
                 ALLOWED_MAKTAB_CHOICES = [
                     Course.Category.QAIDA,
                     Course.Category.NAZRA,
                     Course.Category.HIFZ,
                     Course.Category.DEENYAT,
                     Course.Category.OTHER,
                 ]
                 # Filter choices
                 self.fields['category'].choices = [
                     c for c in Course.Category.choices if c[0] in ALLOWED_MAKTAB_CHOICES
                 ]

        # Tactical styling (Removed) - Only placeholders
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label

    class Meta:
        model = Course
        fields = [
            "title", "category", "description", "instructors", 
            "admission_fee", "course_fee", "fee_type",
            "start_date", "end_date", "capacity", "is_active"
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "instructors": forms.CheckboxSelectMultiple(),
        }

class EnrollmentForm(forms.ModelForm):
    def __init__(self, *args, institution=None, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if institution:
            self.fields['student'].queryset = Student.objects.filter(institution=institution, is_active=True)
        
        # Tactical styling
        for field in self.fields.values():
            field.widget.attrs['placeholder'] = field.label

    class Meta:
        model = Enrollment
        fields = [
            "student", "enrollment_date", "roll_no",
            "admission_fee_discount", "agreed_admission_fee",
            "course_fee_discount", "agreed_course_fee",
            "fee_start_month", "fee_type_override"
        ]
        widgets = {
            "enrollment_date": forms.DateInput(attrs={"type": "date"}),
            "fee_start_month": forms.DateInput(attrs={"type": "date"}),
        }

class ClassSessionForm(forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = [
            "date", "start_time", "end_time", 
            "session_type", "topic", "notes"
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

class FacilityForm(forms.ModelForm):
    class Meta:
        model = Facility
        fields = ["name", "facility_type", "is_available"]

class DailyAttendanceDateForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

class AttendanceReportForm(forms.Form):
    start_date = forms.DateField(
        label="آغاز تاریخ",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label="اختتامی تاریخ",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500 text-sm",
            )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "اختتامی تاریخ، آغاز تاریخ سے پہلے نہیں ہو سکتی۔"
            )
        return cleaned_data

class StudentFeeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_classes = "w-full rounded-lg border-gray-300 focus:border-emerald-500 focus:ring-emerald-500 text-sm"
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} {base_classes}".strip()

    class Meta:
        model = Fee
        # ✅ اپڈیٹ: نئے ماڈل کے مطابق late_fee, discount اور month شامل کیے گئے
        fields = ["title", "month", "amount_due", "late_fee", "discount", "due_date"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "month": forms.DateInput(attrs={"type": "date"}), # مہینے کے لیے بھی ڈیٹ پکر
        }