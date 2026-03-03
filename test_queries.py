from app.models import Student, Staff, Attendance, Course, Institution
from sqlmodel import select, func, Session, create_engine
import os

engine = create_engine('sqlite:///db.sqlite3')
session = Session(engine)

def test_queries():
    try:
        print("Testing select(Staff.inst_id)...")
        stmt = select(Staff.inst_id)
        print("Success:", stmt)
    except Exception as e:
        print("Failed select(Staff.inst_id):", e)
        
    try:
        print("Testing select(Attendance.inst_id)...")
        stmt = select(Attendance.inst_id)
        print("Success:", stmt)
    except Exception as e:
        print("Failed select(Attendance.inst_id):", e)

    try:
        # Simulate loading an object
        print("Fetching first staff...")
        staff = session.exec(select(Staff)).first()
        if staff:
            print(f"Staff loaded. inst_id: {staff.inst_id}")
        else:
            print("No staff found.")
    except Exception as e:
        print("Failed to access staff.inst_id instance:", e)
        import traceback
        traceback.print_exc()

test_queries()
