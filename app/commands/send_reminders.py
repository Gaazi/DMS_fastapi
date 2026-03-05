"""
send_reminders.py
──────────────────
Overdue/Pending fees کے لیے SMS reminders بھیجتا ہے۔

چلائیں:
  .venv/Scripts/python -m app.commands.send_reminders
  .venv/Scripts/python -m app.commands.send_reminders --dry-run  (صرف log، SMS نہیں)
"""
import logging
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("dms.commands")


def main(dry_run: bool = False):
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.finance import Fee
    from app.models.people import Student

    log.info("=" * 55)
    log.info(f"📱 Fee Reminders {'[DRY RUN]' if dry_run else ''} شروع")
    log.info("=" * 55)

    with Session(engine) as session:
        # Overdue fees
        overdue = session.exec(
            select(Fee).where(Fee.status == "overdue")
        ).all()

        # Pending fees (30+ دن پرانی)
        import datetime
        threshold = datetime.date.today() - datetime.timedelta(days=30)
        pending = session.exec(
            select(Fee).where(
                Fee.status == "pending",
                Fee.due_date < threshold
            )
        ).all()

        all_fees = overdue + pending
        log.info(f"📋 {len(overdue)} overdue + {len(pending)} pending (30+ دن) = {len(all_fees)} کل")

        if not all_fees:
            log.info("✅ کوئی reminder نہیں بھیجنا")
            return

        sent = 0
        skipped = 0

        for fee in all_fees:
            student = session.get(Student, fee.student_id)
            if not student or not student.mobile:
                skipped += 1
                continue

            msg = (
                f"آداب {student.name}! "
                f"آپ کی فیس '{fee.title}' "
                f"(رقم: {fee.amount_due - fee.amount_paid:.0f}) "
                f"واجب الادا ہے۔ "
                f"برائے کرم جلد ادا کریں۔ شکریہ"
            )

            if dry_run:
                log.info(f"  [DRY] → {student.mobile}: {msg[:60]}...")
            else:
                try:
                    from app.logic.notifications import send_sms
                    send_sms(student.mobile, msg)
                    log.info(f"  ✅ SMS بھیجا → {student.name} ({student.mobile})")
                    sent += 1
                except Exception as e:
                    log.error(f"  ❌ SMS ناکام → {student.name}: {e}")

    log.info("=" * 55)
    if dry_run:
        log.info(f"[DRY RUN] {len(all_fees)} reminders چیک کیے، کوئی SMS نہیں بھیجا")
    else:
        log.info(f"✅ مکمل! {sent} SMS بھیجے، {skipped} skip (موبائل نہیں)")
    log.info("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fee reminders بھیجیں")
    parser.add_argument("--dry-run", action="store_true", help="صرف log کریں، SMS نہیں")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
