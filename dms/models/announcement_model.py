from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .audit_model import AuditModel

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: Announcement (Line 11)
   - Fields: audience, target_parents, is_published, pinned, expiry_date
   - Properties: is_expired
"""

class Announcement(AuditModel):
    class Audience(models.TextChoices):
        ALL = "all", "سب کے لیے"
        TEACHERS = "teachers", "صرف اساتذہ"
        STUDENTS = "students", "صرف طلبہ"
        PARENTS = "parents", "صرف سرپرست"

    # 'Institution' کو کوٹس میں رکھنا بہتر ہے تاکہ امپورٹ ایرر نہ آئے
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=255, verbose_name=_("عنوان"))
    content = models.TextField(verbose_name=_("تفصیلِ اعلان"))
    
    target_audience = models.CharField(
        max_length=20, 
        choices=Audience.choices, 
        default=Audience.ALL,
        verbose_name=_("مخاطب")
    )
    
    target_parents = models.ManyToManyField(
        'Parent', 
        blank=True, 
        related_name="targeted_announcements", 
        verbose_name="مخصوص والدین"
    )

    is_published = models.BooleanField(default=False, verbose_name="شائع شدہ")
    is_active = models.BooleanField(default=True, verbose_name=_("فعال ہے؟"))
    pinned = models.BooleanField(default=False, verbose_name=_("اوپر پن کریں؟"))

    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField(
        null=True, blank=True, 
        verbose_name=_("ختم ہونے کی تاریخ"),
        help_text="اس تاریخ کے بعد اعلان خود بخود ہٹ جائے گا"
    )

    class Meta:
        # یہاں app_label لازمی لگائیں کیونکہ یہ فولڈر کے اندر ہے
        app_label = 'dms' 
        ordering = ["-pinned", "-created_at"]
        verbose_name = _("اعلان")
        verbose_name_plural = _("اعلانات")

    def __str__(self):
        return self.title

    @property
    def is_expired(self):
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False