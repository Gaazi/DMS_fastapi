from django.core.management.base import BaseCommand
from django.utils import timezone
from dms.models import Fee  # یقینی بنائیں کہ 'dms' آپ کی ایپ کا درست نام ہے

class Command(BaseCommand):
    help = 'تاریخ گزر جانے والی فیسوں کو خودکار طور پر Overdue مارک کریں'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        
        # 1. وہ ریکارڈز تلاش کریں جن کی تاریخ گزر چکی ہے اور وہ ابھی تک ادا نہیں ہوئے
        overdue_queryset = Fee.objects.filter(
            due_date__lt=today,
            status__in=[Fee.Status.PENDING, Fee.Status.PARTIAL]
        ).exclude(status=Fee.Status.WAIVED)

        total_found = overdue_queryset.count()

        if total_found == 0:
            self.stdout.write(self.style.SUCCESS("کوئی ریکارڈ اپڈیٹ کرنے کی ضرورت نہیں ہے۔"))
            return

        # 2. ریکارڈز کو اپڈیٹ کرنا
        # ہم باری باری سیو کریں گے تاکہ ماڈل کے اندر موجود 'save' لاجک (Status Update) صحیح چلے
        count = 0
        for fee in overdue_queryset:
            try:
                # ماڈل کا save() خود بخود update_status() کو کال کرے گا
                fee.save() 
                count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"ID {fee.id} کو اپڈیٹ کرنے میں غلطی: {str(e)}"))

        # 3. حتمی رپورٹ
        self.stdout.write(
            self.style.SUCCESS(f'کامیابی: {count} طلبہ کی فیس کو "Overdue" کر دیا گیا ہے۔')
        )