"""
backfill_reg_ids.py
────────────────────
جن institutions کا reg_id خالی ہو انہیں خودکار ID دیتا ہے۔

چلائیں:
  .venv/Scripts/python -m app.commands.backfill_reg_ids
"""
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("dms.commands")


def main():
    from sqlmodel import Session, select
    from app.db.session import engine
    from app.models.foundation import Institution

    log.info("=" * 55)
    log.info("🔢 Reg ID Backfill شروع")
    log.info("=" * 55)

    with Session(engine) as session:
        institutions = session.exec(
            select(Institution).order_by(Institution.id)
        ).all()

        total = len(institutions)
        if total == 0:
            log.warning("کوئی institution نہیں ملی")
            return

        log.info(f"📋 {total} institutions ملی")

        updated = 0
        skipped = 0

        for inst in institutions:
            if not inst.reg_id:
                # reg_id generate کریں: INS-001 format
                new_id = f"INS-{inst.id:03d}"
                inst.reg_id = new_id
                session.add(inst)
                log.info(f"  ✅ Updated: ID {inst.id} → {new_id} ({inst.name})")
                updated += 1
            else:
                log.info(f"  ─  Skipped: ID {inst.id} ({inst.reg_id}) — پہلے سے موجود")
                skipped += 1

        session.commit()

    log.info("=" * 55)
    log.info(f"✅ مکمل! Updated: {updated}, Skipped: {skipped}")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
