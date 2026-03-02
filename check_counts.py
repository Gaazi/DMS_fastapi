import sqlite3
conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()
tables = ["dms_staffadvance", "dms_student", "dms_staff", "auth_user"]
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"Table {table}: {count} records")
conn.close()
