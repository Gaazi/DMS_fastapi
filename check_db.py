import sqlite3
import os

db_path = "db.sqlite3"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    tables = ["dms_staffadvance", "dms_student", "dms_enrollment"]
    for table in tables:
        print(f"\n--- {table} ---")
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        for col in columns:
            print(col)
    conn.close()
else:
    print(f"{db_path} not found")

