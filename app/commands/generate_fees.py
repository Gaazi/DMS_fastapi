"""
generate_fees.py
─────────────────
تمام approved institutions کے لیے ماہانہ fees خودکار generate کرتا ہے۔

چلائیں:
  .venv/Scripts/python -m app.commands.generate_fees
  .venv/Scripts/python -m app.commands.generate_fees --month 3 --year 2026
"""
import sys
import argparse
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("dms.commands")


def main(month: int = None, year: int = None):
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.foundation import Institution
    from app.logic.finance import FinanceLogic

    now = datetime.datetime.now()
    month = month or now.month
    year = year or now.year

    log.info("=" * 55)
    log.info(f"📅 ماہانہ Fee Generation شروع: {year}-{month:02d}")
    log.info("=" * 55)

    with Session(engine) as session:
        institutions = session.exec(
            select(Institution).where(Institution.is_approved == True)
        ).all()

        total_inst = len(institutions)
        total_generated = 0

        log.info(f"🏫 {total_inst} approved institutions ملی")

        for inst in institutions:
            try:
                fm = FinanceLogic(session, inst, current_user=None)
                count = fm.auto_generate_fees(year=year, month=month)
                total_generated += count
                if count > 0:
                    log.info(f"  ✅ {inst.name}: {count} fees generate ہوئیں")
                else:
                    log.info(f"  ─  {inst.name}: کوئی نئی fee نہیں")
            except Exception as e:
                log.error(f"  ❌ {inst.name}: Error — {e}")

    log.info("=" * 55)
    log.info(f"✅ مکمل! کل {total_generated} fees generate ہوئیں")
    log.info("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ماہانہ fees generate کریں")
    parser.add_argument("--month", type=int, default=None, help="مہینہ (1-12)")
    parser.add_argument("--year", type=int, default=None, help="سال (مثلاً 2026)")
    args = parser.parse_args()
    main(month=args.month, year=args.year)
