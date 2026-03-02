from django.db import models, transaction
from django.conf import settings
from decimal import Decimal
from django.utils import timezone
from .audit_model import AuditModel
from autoslug import AutoSlugField
from django.utils.text import slugify

def unicode_slugify(value):
    return slugify(value, allow_unicode=True)

User = settings.AUTH_USER_MODEL

class Gender(models.TextChoices):
    MALE = "male", "لڑکا"
    FEMALE = "female", "لڑکی"

# 1. بنیادی ماڈل (یہ ڈیٹا بیس میں ٹیبل نہیں بنائے گا، صرف خوبیاں منتقل کرے گا)
class Person(AuditModel):
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s")
    reg_id = models.CharField(max_length=20, unique=True, blank=True, null=True, editable=False, verbose_name="رجسٹریشن نمبر")
    name = models.CharField(max_length=200, verbose_name="نام")
    father_name = models.CharField(max_length=200, verbose_name="والد کا نام", blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, default=Gender.MALE, verbose_name="جنس")
    mobile = models.CharField(max_length=20, blank=True, null=True, verbose_name="موبائل نمبر")
    mobile2 = models.CharField(max_length=20, blank=True, null=True, verbose_name="موبائل نمبر 2")
    email = models.EmailField(blank=True, null=True, verbose_name="ای میل")
    address = models.TextField(blank=True, null=True, verbose_name="پتہ")
    is_active = models.BooleanField(default=True, verbose_name="فعال ہے؟")

    class Meta:
        abstract = True # یہ لائن ضروری ہے تاکہ الگ ٹیبل نہ بنے

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if not self.reg_id and self.institution_id:
            try:
                from .foundation_model import Institution
                inst = Institution.objects.get(pk=self.institution_id)
                
                inst_reg = inst.reg_id or "INS"
                # Determine prefix based on class
                prefix = "P" # Default
                if self.__class__.__name__ == 'Staff': prefix = "E"
                elif self.__class__.__name__ == 'Student': prefix = "S"
                elif self.__class__.__name__ == 'Parent': prefix = "G"
                elif self.__class__.__name__ == 'Admin': prefix = "A"
                
                start_str = f"{inst_reg}-{prefix}-"
                
                # We need to filter based on the Concrete Model
                manager = self.__class__.objects
                qs = manager.all_with_deleted() if hasattr(manager, 'all_with_deleted') else manager.all()
                
                last_obj = qs.filter(
                    institution_id=self.institution_id,
                    reg_id__startswith=start_str
                ).order_by('reg_id').last()
                
                seq = 1
                if last_obj and last_obj.reg_id:
                    try:
                        last_seq_str = last_obj.reg_id.split('-')[-1]
                        seq = int(last_seq_str) + 1
                    except (IndexError, ValueError):
                        seq = 1
                
                self.reg_id = f"{start_str}{seq:04d}"
                print(f"Generated Reg ID successfully: {self.reg_id} for {self.name} ({self.__class__.__name__})")
            except Exception as e:
                print(f"CRITICAL Error generating Reg ID in people_model.py: {e}")
                import traceback
                traceback.print_exc()
                # Don't block save, let it proceed (reg_id might be null)

        super().save(*args, **kwargs)
        
        if is_new:
            # کیشے کلیئر کرنے کی مشترکہ لاجک
            from django.core.cache import cache
            cache.delete(f"inst_{self.institution_id}_main_stats")

# 1. مرکزی اسٹاف ماڈل
from ..logic.roles import Role
from ..logic.groups import RoleGroupManager

class Staff(Person):
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.TEACHER, verbose_name="عہدہ")
    photo = models.ImageField(upload_to="staff/", blank=True, null=True, verbose_name="تصویر")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="بنیادی تنخواہ")
    hire_date = models.DateField(null=True, blank=True, verbose_name="تاریخ تقرری")
    shift_start = models.TimeField(null=True, blank=True, verbose_name="ڈیوٹی شروع")
    shift_end = models.TimeField(null=True, blank=True, verbose_name="ڈیوٹی ختم")
    current_advance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="موجودہ ایڈوانس")
    notes = models.TextField(blank=True)

    @property
    def full_name(self):
        return self.name

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    @property
    def detailed_str(self):
        return f"{self.name} [ID:{self.pk}] - {self.institution.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.user:
            RoleGroupManager.assign_user(self.user, self.role)

    def delete(self, *args, **kwargs):
        inst_id = self.institution_id
        if self.user:
            RoleGroupManager.remove_user(self.user)
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.delete(f"inst_{inst_id}_main_stats")

    class Meta:
        ordering = ("name",)
        verbose_name = "رکنِ عملہ"
        verbose_name_plural = "ارکانِ عملہ"

class StaffAdvance(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="advances")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="رقم")
    date = models.DateField(auto_now_add=True, verbose_name="تاریخ")
    is_adjusted = models.BooleanField(default=False, verbose_name="تنخواہ میں کٹ چکا ہے؟")

    def save(self, *args, **kwargs):
        # 1. Get the old state from DB before saving
        old_amount = Decimal("0.00")
        old_adjusted = False
        
        if self.pk:
            try:
                original = StaffAdvance.objects.get(pk=self.pk)
                old_amount = original.amount
                old_adjusted = original.is_adjusted
            except StaffAdvance.DoesNotExist:
                pass # New object with forced PK? Unlikely but safe.

        super().save(*args, **kwargs)

        # 2. Calculate impact on Staff Balance
        # Logic: 
        # - If it WAS NOT adjusted, it contributed to debt (+old_amount).
        # - If it IS NOT adjusted, it contributes to new debt (+self.amount).
        # - So, remove old contribution, add new contribution.
        
        balance_change = Decimal("0.00")
        
        # Remove old effect
        if not old_adjusted:
            balance_change -= old_amount
            
        # Add new effect
        if not self.is_adjusted:
            balance_change += self.amount
            
        if balance_change != 0:
            self.staff.current_advance += balance_change
            self.staff.save()

    def delete(self, *args, **kwargs):
        # If it was outstanding, remove from debt. If adjusted, it wasn't debt anyway.
        if not self.is_adjusted:
            self.staff.current_advance -= self.amount
            self.staff.save()
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.staff.name} - {self.amount} ({self.date})"

# 2. Parent Model
class Parent(Person):
    class Relation(models.TextChoices):
        FATHER = "father", "والد"
        MOTHER = "mother", "والدہ"
        GUARDIAN = "guardian", "قانونی سرپرست"
        RELATIVE = "relative", "رشتہ دار"
        OTHER = "other", "دیگر"

    relationship = models.CharField(max_length=20, choices=Relation.choices, default=Relation.GUARDIAN, verbose_name="رشتہ")

    
    @property
    def full_name(self):
        return self.name

    def __str__(self):
        return f"{self.name} ({self.get_relationship_display()})"

    @property
    def detailed_str(self):
         return f"{self.name} [ID:{self.pk}] - {self.institution.name}"

    class Meta:
        verbose_name = "سرپرست"
        verbose_name_plural = "سرپرستان"

# 3. Student Model
class Student(Person):
    slug = AutoSlugField(populate_from='name', unique_with=['institution'], always_update=True, verbose_name="URL Slug", null=True, blank=True, slugify=unicode_slugify)
    # Roll No Moved to Enrollment Model
    photo = models.ImageField(upload_to="students/", blank=True, null=True, verbose_name="تصویر")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="تاریخ پیدائش")
    blood_group = models.CharField(max_length=5, blank=True, null=True, verbose_name="بلڈ گروپ")
    
    guardian_name = models.CharField(max_length=200, blank=True, verbose_name="سرپرست کا نام")
    guardian_relation = models.CharField(max_length=100, blank=True, verbose_name="سرپرست سے رشتہ")
    notes = models.TextField(blank=True, verbose_name="نوٹس")
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), verbose_name="بٹوہ (Wallet Balance)")
    enrollment_date = models.DateField(default=timezone.now, verbose_name="تاریخ داخلہ")
    
    parents = models.ManyToManyField('Parent', related_name="students", blank=True, verbose_name="منسلک والدین/اکاؤنٹ")

    def __str__(self):
        return f"{self.name} ({self.reg_id or 'No Reg ID'})"

    @property
    def full_name(self):
        return self.name

    @property
    def detailed_str(self):
        return f"{self.name} [Reg:{self.reg_id or 'N/A'}] ({self.institution.name})"

    def save(self, *args, **kwargs):
        # Roll No Logic Removed from here
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        inst_id = self.institution_id
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.delete(f"inst_{inst_id}_main_stats")

    class Meta:
        ordering = ("name",)
        verbose_name = "طالب علم"
        verbose_name_plural = "طلبہ"

# Enrollment needs to stay valid
class Enrollment(AuditModel):
    class Status(models.TextChoices):
        PENDING = "pending", "منتظر منظوری"
        ACTIVE = "active", "جاری"
        COMPLETED = "completed", "مکمل"
        DROPPED = "dropped", "چھوڑ دیا"
        PAUSED = "paused", "روکا ہوا"

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey('dms.Course', on_delete=models.CASCADE, related_name="enrollments")
    enrollment_date = models.DateField(default=timezone.now)
    roll_no = models.CharField(max_length=50, blank=True, null=True, verbose_name="کلاس رول نمبر")

    admission_fee_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="داخلہ رعایت")
    agreed_admission_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="واجب الادا داخلہ فیس")
 
    course_fee_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="کورس فیس رعایت")
    agreed_course_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="واجب الادا ماہانہ فیس")

    fee_start_month = models.DateField(null=True, blank=True, verbose_name="فیس کا آغاز (مہینہ)")
    
    FEE_TYPE_CHOICES = [("one_time", "ون ٹائم"), ("installment", "قسط"), ("monthly", "ماہانہ فیس"), ("free", "مفت")]
    fee_type_override = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES, null=True, blank=True, verbose_name="مخصوص فیس کا طریقہ (Override)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return f"{self.student.name}"
        
    def calculate_fees(self):
        if hasattr(self, 'admission_discount_percent') and self.admission_discount_percent:
            self.admission_fee_discount = (self.course.admission_fee * Decimal(self.admission_discount_percent)) / 100
        if hasattr(self, 'course_discount_percent') and self.course_discount_percent:
            self.course_fee_discount = (self.course.course_fee * Decimal(self.course_discount_percent)) / 100

        if self.course_id:
            actual_adm = self.course.admission_fee or 0
            if self.admission_fee_discount:
                self.agreed_admission_fee = max(Decimal('0'), actual_adm - self.admission_fee_discount)
            else:
                self.agreed_admission_fee = actual_adm
                self.admission_fee_discount = Decimal('0')

            actual_course = self.course.course_fee or 0
            if self.course_fee_discount:
                self.agreed_course_fee = max(Decimal('0'), actual_course - self.course_fee_discount)
            else:
                self.agreed_course_fee = actual_course
                self.course_fee_discount = Decimal('0')
            
        if not self.fee_start_month:
            self.fee_start_month = timezone.now().date().replace(day=1)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Auto Roll-No Logic for Course
        if is_new and not self.roll_no and self.course_id:
            with transaction.atomic():
                 c_count = Enrollment.objects.filter(course_id=self.course_id).count() + 1
                 self.roll_no = f"{c_count:03d}"
                 
        self.calculate_fees()
        super().save(*args, **kwargs)
        if is_new:
            from dms.logic.finance import FinanceManager
            FinanceManager.generate_initial_fees_for_enrollment(self)

    class Meta:
        unique_together = ("student", "course")
        verbose_name = "داخلہ"
        verbose_name_plural = "داخلہ جات"