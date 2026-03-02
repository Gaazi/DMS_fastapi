from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from autoslug import AutoSlugField

User = settings.AUTH_USER_MODEL
from .audit_model import AuditModel

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: Institution (Line 21) - Primary organizational unit
Class: Course (Line 49) - Courses, Fees, and Categories
Class: Facility (Line 84) - Rooms, Halls, and assets
"""




# ==========================================
# 1. بنیادی ڈھانچہ (Foundation Models)
# ==========================================

# --- Migration Helpers (Do not remove) ---
def unicode_slugify(value):
    return slugify(value, allow_unicode=False)

def get_institution_slug_source(instance):
    return instance.name_in_english or instance.name
# -----------------------------------------

def institution_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/institutions/<slug>/<filename>
    return 'institutions/{0}/{1}'.format(instance.slug, filename)


class Institution(AuditModel):
    class Type(models.TextChoices):
        MASJID = "masjid", "مسجد"
        MADRASA = "madrasa", "مدرسہ"
        MAKTAB = "maktab", "مکتب"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "فعال"
        INACTIVE = "inactive", "غیر فعال"
        SUSPENDED_PAYMENT = "suspended_payment", "معطل (فیس)"
        SUSPENDED_POLICY = "suspended_policy", "معطل (خلاف ورزی)"
        MAINTENANCE = "maintenance", "مینٹیننس"
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    reg_id = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="رجسٹریشن نمبر")
    name = models.CharField(max_length=50, verbose_name="ادارے کا نام انگلش میں لکھیں")
    name_in_urdu = models.CharField(max_length=200, verbose_name="ادارے کا نام اردو میں لکھیں", blank=True, null=True)
    slug = AutoSlugField(populate_from='name', unique=True, editable=True, always_update=True, blank=True, null=True)
    type = models.CharField(max_length=20, choices=Type.choices, verbose_name="قسم")
    phone = models.CharField(max_length=20, blank=True, verbose_name="فون نمبر")
    email = models.EmailField(blank=True, verbose_name="ای میل")
    address = models.TextField(blank=True, verbose_name="پتہ")
    logo = models.ImageField(upload_to=institution_directory_path, blank=True, null=True)
    is_approved = models.BooleanField(default=False, verbose_name="منظور شدہ")
    active_date = models.DateField(null=True, blank=True, verbose_name="فعال ہونے کی تاریخ")
    status = models.CharField(max_length=20, choices=AccountStatus.choices, default=AccountStatus.ACTIVE, verbose_name="حیثیت")
    is_default = models.BooleanField(default=False, verbose_name="طے شدہ ادارہ")

    def save(self, *args, **kwargs):
        # Ensure only one default institution exists per user
        if self.is_default and self.user:
            Institution.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        if not self.reg_id:
            # Generate Unique ID based on Type
            prefix_map = {
                self.Type.MASJID: "MSJ",
                self.Type.MADRASA: "MDR",
                self.Type.MAKTAB: "MKT"
            }
            prefix = prefix_map.get(self.type, "INS")
            
            # Find the last ID for this type to increment
            manager = Institution.objects
            qs = manager.all_with_deleted() if hasattr(manager, 'all_with_deleted') else manager.all()
            last_inst = qs.filter(type=self.type).exclude(reg_id__isnull=True).order_by('reg_id').last()
            
            new_seq = 1
            if last_inst and last_inst.reg_id:
                try:
                    # Extract last 3 digits
                    last_seq = int(last_inst.reg_id.split('-')[-1])
                    new_seq = last_seq + 1
                except (IndexError, ValueError):
                    new_seq = 1
            
            self.reg_id = f"{prefix}-{new_seq:03d}"
            
        # 2. Generate Slug Manually (Fallback / Safety)
        if not self.name and not self.slug:
            self.slug = self.reg_id
            
        super().save(*args, **kwargs)

    def __str__(self):
        if self.name_in_urdu:
            return f"{self.name_in_urdu}"
        return f"{self.name}"

    class Meta:
        app_label = 'dms'  # فولڈر اسٹرکچر کے لیے لازمی
        ordering = ("name",)
        verbose_name = "ادارہ"
        verbose_name_plural = "ادارے"


# ==========================================
# 2. بنیادی ڈھانچہ (Foundation Models)
# ==========================================
class Course(AuditModel):
    class Category(models.TextChoices):
        # --- مکتب اور ابتدائی تعلیم ---
        QAIDA = "qaida", "نورانی قاعدہ"
        NAZRA = "nazra", "ناظرہ قرآن"
        HIFZ = "hifz", "حفظ قرآن"
        DEENYAT = "deenyat", "دینیات"
        OTHER = "other", "دیگر"
        
        # --- درس نظامی و تخصص (مدرسہ) ---
        DARS = "dars", "درس نظامی"
        AALIM = "aalim", "عالم کورس"
        IFTA = "ifta", "افتاء"
        TAFSEER = "tafseer", "تفسیر"
        ARABIC_ADAB = "arabic_adab", "عربی ادب"
        ISLAMYAT = "islamyat", "اسلامیات"

    class FeeType(models.TextChoices):
        ONE_TIME = "one_time", "ون ٹائم"
        INSTALLMENT = "installment", "قسط"
        MONTHLY = "monthly", "ماہانہ فیس"
        FREE = "free", "مفت"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="courses")
    
    # بنیادی معلومات
    title = models.CharField(max_length=200, verbose_name="کورس کا نام")
    category = models.CharField(max_length=50, choices=Category.choices, verbose_name="زمرہ")
    description = models.TextField(blank=True, verbose_name="تفصیل")
    
    # فیس کا نظام (Standard Fees for this Course)
    fee_type = models.CharField(max_length=20, choices=FeeType.choices, default=FeeType.MONTHLY, verbose_name="فیس کی قسم")
    admission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="داخلہ فیس")
    course_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="کورس فیس")
    
    # لاجسٹکس
    start_date = models.DateField(null=True, blank=True, verbose_name="شروع ہونے کی تاریخ")
    end_date = models.DateField(null=True, blank=True, verbose_name="ختم ہونے کی تاریخ")
    capacity = models.PositiveIntegerField(null=True, blank=True, verbose_name="طلبہ کی گنجائش")
    instructors = models.ManyToManyField('dms.Staff', blank=True, related_name="courses_taught", verbose_name="اساتذہ")
    is_active = models.BooleanField(default=True, verbose_name="فعال ہے؟")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from django.core.cache import cache
            cache.delete(f"inst_{self.institution_id}_main_stats")

    def delete(self, *args, **kwargs):
        inst_id = self.institution_id
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.delete(f"inst_{inst_id}_main_stats")

    def __str__(self):
        return f"{self.title} ({self.institution.name})"

    class Meta:
        app_label = 'dms'
        ordering = ['title']
        verbose_name = "کورس"
        verbose_name_plural = "کورسز"


# ==========================================
# 3. بنیادی ڈھانچہ (Foundation Models)
# ==========================================
class Facility(AuditModel):
    class Type(models.TextChoices):
        CLASSROOM = "classroom", "کلاس روم"
        PRAYER_HALL = "prayer_hall", "ہال / مسجد"
        OFFICE = "office", "دفتر"
        OTHER = "other", "دیگر"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="facilities")
    name = models.CharField(max_length=200, verbose_name="سہولت کا نام")
    facility_type = models.CharField(max_length=50, choices=Type.choices, verbose_name="قسم")
    is_available = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from django.core.cache import cache
            cache.delete(f"inst_{self.institution_id}_main_stats")

    def delete(self, *args, **kwargs):
        inst_id = self.institution_id
        super().delete(*args, **kwargs)
        from django.core.cache import cache
        cache.delete(f"inst_{inst_id}_main_stats")

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'dms'
        verbose_name = "سہولت"
        verbose_name_plural = "سہولیات"