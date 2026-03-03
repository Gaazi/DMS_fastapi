import sqlite3
import os

def check(table):
    try:
        db_path = 'db.sqlite3'
        if not os.path.exists(db_path):
            print(f"Database not found at {db_path}")
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        print(f"--- {table} ---")
        rows = cursor.fetchall()
        if not rows:
            print("Table empty or not found.")
        for c in rows:
            print(f"Column: {c[1]}, Type: {c[2]}")
        conn.close()
    except Exception as e:
        print(f"Error checking {table}: {e}")

check('dms_student')
check('dms_staff')
check('dms_institution')
check('dms_attendance')
check('dms_classsession')
