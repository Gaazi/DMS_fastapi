import sqlite3

def fix_db():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    tables = [
        "dms_institution", "dms_course", "dms_facility", "dms_staff", "dms_parent", 
        "dms_student", "dms_enrollment", "dms_fee", "dms_fee_payment", 
        "dms_wallettransaction", "dms_donor", "dms_income", "dms_expense", 
        "dms_classsession", "dms_staff_attendance", "dms_attendance", 
        "dms_exam", "dms_examresult", "dms_announcement", "dms_itemcategory", 
        "dms_inventoryitem", "dms_assetissue", "dms_timetableitem", 
        "dms_backup", "dms_activitylog"
    ]
    
    for table in tables:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at DATETIME")
            print(f"Added deleted_at to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"deleted_at already exists in {table}")
            else:
                print(f"Error for {table}: {e}")
                
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_db()
