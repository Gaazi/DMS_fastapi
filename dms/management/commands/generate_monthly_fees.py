from django.core.management.base import BaseCommand
from django.utils import timezone
from dms.models import Institution
from dms.logic.finance import FinanceManager

class Command(BaseCommand):
    help = 'Fully automated script: generates monthly fees for all active enrollments across all approved institutions without human intervention.'

    def handle(self, *args, **kwargs):
        self.stdout.write("-----------------------------------------------------")
        self.stdout.write("Starting SERVER CRON JOB: Monthly Fee Generation...")
        
        now = timezone.now()
        
        # Get only active/approved institutions
        institutions = Institution.objects.filter(is_approved=True)
        total_institutions = institutions.count()
        total_generated = 0
        
        self.stdout.write(f"Found {total_institutions} active institutions to process.")
        
        for inst in institutions:
            # Run using the global 'System' context (bypasses permissions check in FinanceManager)
            fm = FinanceManager(user=None, institution=inst)
            try:
                # Triggers the generation for this month
                count = fm.auto_generate_fees(year=now.year, month=now.month)
                total_generated += count
                if count > 0:
                    self.stdout.write(self.style.SUCCESS(f"  [+] Generated {count} fees for => {inst.name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [x] Error for {inst.name}: {e}"))
                
        self.stdout.write("-----------------------------------------------------")
        self.stdout.write(self.style.SUCCESS(f"CRON JOB COMPLETED. Total fees automatically generated globally: {total_generated}"))
        self.stdout.write("-----------------------------------------------------")
