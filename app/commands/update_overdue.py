"""
update_overdue.py
──────────────────
تاریخ گزر جانے والی (due_date < آج) fees کو OVERDUE mark کرتا ہے۔

چلائیں:
  .venv/Scripts/python -m app.commands.update_overdue
"""
import logging
import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("dms.commands")


def main():
    from sqlmodel import Session, select, col
    from app.db.session import engine
    from app.models.finance import Fee

    today = datetime.date.today()

    log.info("=" * 55)
    log.info(f"⏰ Overdue Fees Update شروع — آج: {today}")
    log.info("=" * 55)

    with Session(engine) as session:
        # وہ fees جن کی due_date گزر گئی اور status pending/partial ہے
        overdue_fees = session.exec(
            select(Fee).where(
                Fee.due_date < today,
                Fee.status.in_(["pending", "partial"]),
            )
        ).all()

        total = len(overdue_fees)

        if total == 0:
            log.info("✅ کوئی overdue fee نہیں — سب ٹھیک ہے!")
            return

        log.info(f"⚠️  {total} fees overdue ہیں — update کر رہے ہیں...")

        count = 0
        for fee in overdue_fees:
            try:
                fee.status = "overdue"
                session.add(fee)
                count += 1
            except Exception as e:
                log.error(f"  ❌ Fee ID {fee.id}: {e}")

        session.commit()

    log.info("=" * 55)
    log.info(f"✅ مکمل! {count} fees کو OVERDUE mark کر دیا گیا")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
