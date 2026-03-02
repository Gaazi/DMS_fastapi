from django.core.management.base import BaseCommand
from dms.models.foundation_model import Institution

class Command(BaseCommand):
    help = 'Backfill registration IDs for existing institutions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting backfill process..."))
        
        # Count total institutions
        total = Institution.objects.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No institutions found."))
            return

        # Fetch all institutions that need updates
        institutions = Institution.objects.all().order_by('id')
        
        updated_count = 0
        skipped_count = 0

        for inst in institutions:
            if not inst.reg_id:
                # The model's save method handles generation logic automatically
                # We force 'save()' to trigger that logic
                inst.save()
                updated_count += 1
                self.stdout.write(f"Updated: ID {inst.id} -> {inst.reg_id}")
            else:
                skipped_count += 1
                self.stdout.write(f"Skipped: ID {inst.id} (Already has {inst.reg_id})")

        self.stdout.write(self.style.SUCCESS(f"Complete! Updated: {updated_count}, Skipped: {skipped_count}"))
