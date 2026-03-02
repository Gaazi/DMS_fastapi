from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .audit_model import AuditModel

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: ClassSession (Line 17)
Class: Staff_Attendance (Line 58)
Class: Attendance (Line 73) - Student attendance linking to sessions
"""

# ==========================================
# 3. حاضری اور کلاسز (Attendance & Sessions)
# ==========================================

class ClassSession(AuditModel):
    class SessionType(models.TextChoices):
        CLASS = "class", "شیڈول کلاس"
        REVISION = "revision", "دہرائی"
        ASSESSMENT = "assessment", "جائزہ/امتحان"
        EVENT = "event", "خصوصی تقریب"
        OTHER = "other", "دیگر"

    # String reference 'Course' استعمال کریں تاکہ سرکلر امپورٹ نہ ہو
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField(default=timezone.now, verbose_name="تاریخ", db_index=True)
    start_time = models.TimeField(null=True, blank=True, verbose_name="آغاز وقت")
    end_time = models.TimeField(null=True, blank=True, verbose_name="اختتامی وقت")
    session_type = models.CharField(max_length=20, choices=SessionType.choices, default=SessionType.CLASS, verbose_name="نشست کی قسم")
    topic = models.CharField(max_length=255, blank=True, verbose_name="موضوع/سبق")
    notes = models.TextField(blank=True, verbose_name="نوٹس")

    def __str__(self):
        return f"{self.course.title} - {self.date}"

    class Meta:
        app_label = 'dms'  # یہ بہت ضروری ہے
        ordering = ("-date", "-id")
        verbose_name = "درس کی نشست"
        verbose_name_plural = "دروس کی نشستیں"

class BaseAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غیر حاضر"
        LATE = "late", "تاخیر"
        EXCUSED = "excused", "رخصت"

    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="%(class)s_records")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT, verbose_name="کیفیت")
    remarks = models.TextField(blank=True, verbose_name="ریمارکس")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

class Staff_Attendance(AuditModel, BaseAttendance):
    # 'Staff' کو بھی سٹرنگ میں لکھیں
    staff_member = models.ForeignKey('Staff', on_delete=models.CASCADE, related_name="daily_attendance")
    date = models.DateField(default=timezone.now, verbose_name="تاریخ", db_index=True)
    is_late = models.BooleanField(default=False, verbose_name="تاخیر سے آمد")

    def __str__(self):
        return f"{self.staff_member.full_name} - {self.date}"

    class Meta:
        app_label = 'dms'
        unique_together = ("staff_member", "date")
        verbose_name = "عملہ کی حاضری"
        verbose_name_plural = "عملہ کی حاضریاں"

class Attendance(AuditModel, BaseAttendance):
    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="session_attendance")

    def __str__(self):
        return f"{self.student.full_name} - {self.session.date}"

    class Meta:
        app_label = 'dms'
        unique_together = ("session", "student")
        verbose_name = "طلبہ حاضری"
        verbose_name_plural = "طلبہ حاضریاں"