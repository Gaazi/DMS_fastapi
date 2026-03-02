from django.db import models
from django.utils.translation import gettext_lazy as _
from .audit_model import AuditModel

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: Exam (Line 15) - Exam terms and scheduling
Class: ExamResult (Line 41) - Marks, percentages, and grading logic
"""

# ==========================================
# 4. امتحانات (Exams & Results)
# ==========================================

class Exam(AuditModel):
    class Term(models.TextChoices):
        FIRST_TERM = "first_term", "سہ ماہی / پہلا ٹرم"
        MID_TERM = "mid_term", "ششماہی / مڈ ٹرم"
        FINAL_TERM = "final_term", "سالانہ / فائنل ٹرم"
        MONTHLY_TEST = "monthly", "ماہانہ ٹیسٹ"
        OTHER = "other", "دیگر"

    # 'Institution' کو سٹرنگ میں رکھیں
    institution = models.ForeignKey('Institution', on_delete=models.CASCADE, related_name="exams")
    title = models.CharField(max_length=200, verbose_name="امتحان کا نام")
    term = models.CharField(max_length=50, choices=Term.choices, default=Term.FINAL_TERM, verbose_name="ٹرم")
    start_date = models.DateField(verbose_name="آغازِ امتحان")
    end_date = models.DateField(verbose_name="اختتامِ امتحان")
    is_active = models.BooleanField(default=True, verbose_name="فعال ہے؟")
    notes = models.TextField(blank=True, verbose_name="اضافی معلومات")

    def __str__(self):
        return f"{self.title} - {self.institution.name}"

    class Meta:
        app_label = 'dms'  # لازمی
        ordering = ("-start_date",)
        verbose_name = "امتحان"
        verbose_name_plural = "امتحانات"

class ExamResult(AuditModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="results")
    # 'Student' اور 'Course' کو سٹرنگ میں رکھیں
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name="exam_results")
    course = models.ForeignKey('Course', on_delete=models.CASCADE, verbose_name="مضمون / پروگرام")
    
    total_marks = models.PositiveIntegerField(default=100, verbose_name="کل نمبر")
    obtained_marks = models.PositiveIntegerField(verbose_name="ح حاصل کردہ نمبر")
    
    teacher_remarks = models.CharField(max_length=255, blank=True, verbose_name="استاد کی رائے")
    recorded_at = models.DateTimeField(auto_now_add=True)

    @property
    def percentage(self):
        if self.total_marks > 0:
            return (self.obtained_marks / self.total_marks) * 100
        return 0

    @property
    def grade(self):
        p = self.percentage
        # ممتاز (A+) عام طور پر 90 یا 95 سے شروع ہوتا ہے
        if p >= 90: return "ممتاز (A+)"
        elif p >= 80: return "جید جدا (A)"
        elif p >= 70: return "جید (B)"
        elif p >= 60: return "مقبول (C)"
        elif p >= 40: return "راسب (D)"
        else: return "فیل (F)"

    def __str__(self):
        # یہاں student.full_name کو محفوظ طریقے سے کال کریں
        return f"{self.student} - {self.exam.title}"

    class Meta:
        app_label = 'dms' # لازمی
        unique_together = ("exam", "student", "course")
        verbose_name = "امتحانی نتیجہ"
        verbose_name_plural = "امتحانی نتائج"