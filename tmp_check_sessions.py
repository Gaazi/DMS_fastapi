from sqlmodel import Session, select
from app.db.session import engine
from app.models import ClassSession, Course

with Session(engine) as session:
    course_id = 8
    sessions = session.exec(select(ClassSession).where(ClassSession.course_id == course_id)).all()
    print(f"Sessions for course {course_id}: {len(sessions)}")
    for s in sessions:
        print(f"ID: {s.id}, Date: {s.date}, Topic: {s.topic}, CourseID: {s.course_id}")
