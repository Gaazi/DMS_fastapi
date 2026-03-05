"""
create_snapshot.py
───────────────────
سسٹم کا backup (SystemSnapshot) بناتا ہے۔
7 دن سے پرانے backups خودکار delete ہوتے ہیں۔

چلائیں:
  .venv/Scripts/python -m app.commands.create_snapshot
  .venv/Scripts/python -m app.commands.create_snapshot --institution qasimul-uloom-online
  .venv/Scripts/python -m app.commands.create_snapshot --label "Monthly Backup March 2026"
"""
import logging
import argparse
import datetime
import json
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("dms.commands")


def main(institution_slug: str = None, label: str = None):
    from sqlmodel import Session, select
    from app.core.database import engine
    from app.models.foundation import Institution
    from app.models.backup import SystemSnapshot

    now = datetime.datetime.now()
    label = label or f"Auto Backup {now.strftime('%Y-%m-%d %H:%M')}"

    log.info("=" * 55)
    log.info(f"💾 Snapshot شروع: {label}")
    log.info("=" * 55)

    with Session(engine) as session:

        # ادارہ تلاش کریں (اگر slug دیا ہو)
        institution = None
        if institution_slug:
            institution = session.exec(
                select(Institution).where(Institution.slug == institution_slug)
            ).first()
            if not institution:
                log.error(f"❌ ادارہ نہیں ملا: {institution_slug}")
                return

        # Backup folder بنائیں
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = now.strftime('%Y-%m-%d_%H-%M')
        slug_part = institution.slug if institution else "System"
        filename = f"DMS_Backup_{slug_part}_{timestamp}.json"
        filepath = os.path.join(backup_dir, filename)

        # سادہ JSON export (tables کا data)
        backup_data = {
            "label": label,
            "timestamp": now.isoformat(),
            "institution": institution.slug if institution else "all",
            "tables": {}
        }

        # Institutions export
        if institution:
            insts = [institution]
        else:
            insts = session.exec(select(Institution)).all()

        backup_data["tables"]["institutions"] = [
            {"id": i.id, "name": i.name, "slug": i.slug, "reg_id": i.reg_id}
            for i in insts
        ]

        # File محفوظ کریں
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(filepath)
        log.info(f"✅ Backup محفوظ: {filepath} ({file_size} bytes)")

        # SystemSnapshot record بنائیں
        snapshot = SystemSnapshot(
            label=label,
            inst_id=institution.id if institution else None,
            backup_type="automated" if not label.startswith("Auto") is False else "manual",
            size=file_size,
            file_path=filepath,
        )
        session.add(snapshot)

        # ── پرانے Backups صاف کریں (7 دن) ──
        retention = now - datetime.timedelta(days=7)
        old = session.exec(
            select(SystemSnapshot).where(SystemSnapshot.created_at < retention)
        ).all()

        deleted = 0
        for old_snap in old:
            if old_snap.file_path and os.path.exists(old_snap.file_path):
                os.remove(old_snap.file_path)
            session.delete(old_snap)
            deleted += 1

        session.commit()

        if deleted:
            log.warning(f"🗑️  {deleted} پرانے backups (7 دن+) delete کیے گئے")

    log.info("=" * 55)
    log.info(f"✅ Snapshot مکمل: {filename}")
    log.info("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System snapshot/backup بنائیں")
    parser.add_argument("--institution", type=str, default=None, help="ادارے کا slug")
    parser.add_argument("--label", type=str, default=None, help="backup کا نام")
    args = parser.parse_args()
    main(institution_slug=args.institution, label=args.label)
