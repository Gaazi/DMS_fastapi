from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from dms.models import Fee, Institution

class Command(BaseCommand):
    help = 'Send reminders for Overdue or Pending fees (simulated for now).'

    def handle(self, *args, **options):
        self.stdout.write("--- Checking for Reminders ---")
        
        # 1. Overdue Fees
        overdue_fees = Fee.objects.filter(status=Fee.Status.OVERDUE)
        
        if overdue_fees.exists():
            self.stdout.write(self.style.WARNING(f"Found {overdue_fees.count()} overdue fees."))
            for fee in overdue_fees:
                # In a real app, send WhatsApp/SMS here
                student = fee.student
                msg = f"Reminder: Dear {student.full_name}, your fee '{fee.title}' of {fee.amount_due} was due on {fee.due_date}. Please pay immediately."
                
                # For now, just logging
                # self.stdout.write(f"-> Would send to {student.contact_number}: {msg}")
                
        else:
            self.stdout.write(self.style.SUCCESS("No overdue fees found."))

        self.stdout.write(self.style.SUCCESS("--- Reminder check complete. ---"))
