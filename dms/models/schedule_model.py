from django.db import models
from .foundation_model import Institution, Course, Facility
from .people_model import Staff
from .audit_model import AuditModel

class TimetableItem(AuditModel):
    class DayOfWeek(models.TextChoices):
        MONDAY = "1", "پیر"
        TUESDAY = "2", "منگل"
        WEDNESDAY = "3", "بدھ"
        THURSDAY = "4", "جمعرات"
        FRIDAY = "5", "جمعہ"
        SATURDAY = "6", "ہفتہ"
        SUNDAY = "7", "اتوار"

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="timetable_items")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="timetable_slots")
    teacher = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="schedule")
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_slots")
    
    day_of_week = models.CharField(max_length=1, choices=DayOfWeek.choices, verbose_name="دن")
    start_time = models.TimeField(verbose_name="شروع وقت")
    end_time = models.TimeField(verbose_name="ختم وقت")
    subject = models.CharField(max_length=200, blank=True, verbose_name="مضمون / سرگرمی")
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_day_of_week_display()} - {self.course.title} ({self.start_time})"

    class Meta:
        verbose_name = "ٹائم ٹیبل آئٹم"
        verbose_name_plural = "ٹائم ٹیبل"
        ordering = ['day_of_week', 'start_time']
