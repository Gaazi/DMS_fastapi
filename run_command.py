"""
run_command.py — DMS Command Runner
─────────────────────────────────────
Django کے manage.py جیسا۔

Usage:
  .venv/Scripts/python run_command.py <command> [options]

Commands:
  generate_fees     -- ماہانہ fees generate کریں
  update_overdue    -- overdue fees mark کریں
  send_reminders    -- SMS reminders بھیجیں
  create_snapshot   -- system backup بنائیں
  backfill_reg_ids  -- missing reg_ids fill کریں

Examples:
  .venv/Scripts/python run_command.py generate_fees
  .venv/Scripts/python run_command.py generate_fees --month 3 --year 2026
  .venv/Scripts/python run_command.py update_overdue
  .venv/Scripts/python run_command.py send_reminders --dry-run
  .venv/Scripts/python run_command.py create_snapshot --institution qasimul-uloom-online
  .venv/Scripts/python run_command.py backfill_reg_ids
"""
import sys

COMMANDS = {
    "generate_fees":    ("app.commands.generate_fees",   "main"),
    "update_overdue":   ("app.commands.update_overdue",  "main"),
    "send_reminders":   ("app.commands.send_reminders",  "main"),
    "create_snapshot":  ("app.commands.create_snapshot", "main"),
    "backfill_reg_ids": ("app.commands.backfill_reg_ids","main"),
}

def show_help():
    print(__doc__)
    print("Available commands:")
    for cmd in COMMANDS:
        print(f"  {cmd}")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        show_help()
        sys.exit(0)

    cmd_name = sys.argv[1]
    if cmd_name not in COMMANDS:
        print(f"❌ Unknown command: '{cmd_name}'")
        print(f"Available: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    # Command module import کریں اور چلائیں
    module_path, func_name = COMMANDS[cmd_name]
    import importlib
    module = importlib.import_module(module_path)

    # باقی args pass کریں
    sys.argv = [cmd_name] + sys.argv[2:]
    getattr(module, func_name)
    
    # argparse استعمال کرتا ہے، اس لیے __main__ سے چلائیں
    import runpy
    runpy.run_module(module_path, run_name="__main__", alter_sys=True)
