from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import date as dt_date, time, datetime
from .base import AuditModel
from sqlalchemy import Column, Integer, ForeignKey

if TYPE_CHECKING:
    from .foundation import Institution, Course
    from .people import Staff, Student

class ClassSession(AuditModel, table=True):
    __tablename__ = "dms_classsession"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="dms_course.id")
    date: dt_date = Field(default_factory=dt_date.today, index=True)
    start_time: Optional[time] = Field(default=None)
    end_time: Optional[time] = Field(default=None)
    session_type: str = Field(default="class", max_length=20)
    topic: str = Field(default="", max_length=255)
    notes: str = Field(default="")

    attendance_records: List["Attendance"] = Relationship(back_populates="session")

class Staff_Attendance(AuditModel, table=True):
    __tablename__ = "dms_staff_attendance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    staff_member_id: int = Field(foreign_key="dms_staff.id")
    date: dt_date = Field(default_factory=dt_date.today, index=True)
    status: str = Field(default="present", max_length=20)
    remarks: str = Field(default="")
    is_late: bool = Field(default=False)
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

class Attendance(AuditModel, table=True):
    __tablename__ = "dms_attendance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    session_id: int = Field(foreign_key="dms_classsession.id")
    student_id: int = Field(foreign_key="dms_student.id")
    status: str = Field(default="present", max_length=20)
    remarks: str = Field(default="")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    session: ClassSession = Relationship(back_populates="attendance_records")
