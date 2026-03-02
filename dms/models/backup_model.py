from django.db import models
from .foundation_model import Institution

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Class: SystemSnapshot (Line 14) - Database and file backup records
"""

class SystemSnapshot(models.Model):
    BACKUP_TYPES = [
        ('manual', 'Manual (یوزر نے لیا)'),
        ('automated', 'Automated (سسٹم نے لیا)'),
    ]
    
    label = models.CharField(max_length=255, verbose_name="لیبل")
    file = models.FileField(upload_to='backups/%Y/%m/%d/', verbose_name="بیک اپ فائل")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, null=True, blank=True, verbose_name="ادارہ")
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, default='manual', verbose_name="بیک اپ کی قسم")
    size = models.BigIntegerField(default=0, verbose_name="سائز (بائٹس)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="بنانے کا وقت")
    notes = models.TextField(blank=True, null=True, verbose_name="نوٹس")

    class Meta:
        verbose_name = "سسٹم اسنیپ شاٹ"
        verbose_name_plural = "سسٹم اسنیپ شاٹس"
        ordering = ['-created_at']

    def __str__(self):
        inst_name = self.institution.name if self.institution else "پورے سسٹم"
        return f"{inst_name} کا بیک اپ - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
