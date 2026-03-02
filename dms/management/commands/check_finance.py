from django.core.management.base import BaseCommand
from django.db.models import Sum
from dms.models import Institution

class Command(BaseCommand):
    help = 'تمام اداروں کا بیلنس چیک کرنا (Optimized)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- فنانس رپورٹ شروع ہو رہی ہے ---"))
        
        # آپ کا پرانا طریقہ سست تھا، یہ طریقہ (annotate) بہت تیز ہے
        # یہ ڈیٹا بیس سے ایک ہی بار میں حساب کر کے لاتا ہے
        institutions = Institution.objects.annotate(
            total_income=Sum('incomes__amount'),
            total_expense=Sum('expenses__amount')
        )

        for inst in institutions:
            income = inst.total_income or 0
            expense = inst.total_expense or 0
            balance = income - expense
            
            self.stdout.write(
                f"ادارہ: {inst.name:<25} | آمدنی: {income:<10.2f} | خرچ: {expense:<10.2f} | بیلنس: {balance:<10.2f}"
            )