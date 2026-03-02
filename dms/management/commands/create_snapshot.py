import io
import os
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from dms.models import Institution, SystemSnapshot
from dms.exporting import export_all_institutions_bundle, export_institutions_bundle

class Command(BaseCommand):
    help = "سسٹم کا خودکار بیک اپ (Snapshot) بناتا ہے"

    def add_arguments(self, parser):
        parser.add_argument('--institution', type=str, help='کسی مخصوص ادارے کا سلگ (Slug)')
        parser.add_argument('--label', type=str, help='بیک اپ کا نام')

    def handle(self, *args, **options):
        inst_slug = options.get('institution')
        label = options.get('label') or f"Auto Backup {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        
        self.stdout.write(self.style.NOTICE(f"بیک اپ شروع ہو رہا ہے: {label}"))
        
        try:
            institution = None
            if inst_slug:
                institution = Institution.objects.get(slug=inst_slug)
                # انفرادی ادارے کا بیک اپ
                archive_bytes = export_institutions_bundle([institution])
            else:
                # پورے سسٹم کا بیک اپ
                archive_bytes = export_all_institutions_bundle()

            # اسنیپ شاٹ ماڈل میں محفوظ کریں
            snapshot = SystemSnapshot(
                label=label,
                institution=institution,
                backup_type='automated' if not options.get('label') else 'manual',
                size=len(archive_bytes)
            )
            
            # فائل کا نام: DMS_Backup_[Slug]_[Date].zip
            timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M')
            slug_part = institution.slug if institution else "System"
            filename = f"DMS_Backup_{slug_part}_{timestamp}.zip"
            
            snapshot.file.save(filename, ContentFile(archive_bytes))
            snapshot.save()
            
            self.stdout.write(self.style.SUCCESS(f"ٹیسٹ بیک اپ مکمل: {snapshot.file.name} ({snapshot.size} بائٹس)"))
            
            # --- آٹو کلین اپ (7 دن سے پرانے بیک اپس کو حذف کرنا) ---
            retention_limit = timezone.now() - timezone.timedelta(days=7)
            old_snapshots = SystemSnapshot.objects.filter(created_at__lt=retention_limit)
            count = old_snapshots.count()
            if count > 0:
                for old in old_snapshots:
                    old.file.delete() # فائل حذف کریں
                    old.delete()      # ریکارڈ حذف کریں
                self.stdout.write(self.style.WARNING(f"{count} پرانے بیک اپس (7 دن سے زیادہ) خودکار طور پر حذف کر دیے گئے۔"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"بیک اپ میں غلطی: {str(e)}"))
