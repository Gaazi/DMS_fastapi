from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Integer, ForeignKey, UniqueConstraint
from datetime import date as dt_date, time, datetime
from app.models.base import AuditModel


if TYPE_CHECKING:
    from app.models.foundation import Institution, Course
    from app.models.people import Staff, Student

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
    
    __table_args__ = (
        UniqueConstraint("course_id", "date", "start_time", name="uq_course_session"),
    )

    attendance_records: List["Attendance"] = Relationship(back_populates="session")
    course: Optional["Course"] = Relationship()

    @property
    def get_session_type_display(self) -> str:
        type_map = {
            "Lecture": "لیکچر (Lecture)",
            "Practice": "پریکٹس (Practice)",
            "Exam": "امتحان (Exam)",
            "class": "کلاس (Class)"
        }
        return type_map.get(self.session_type, self.session_type)

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

    @property
    def get_status_display(self) -> str:
        return self.status.capitalize()

class Attendance(AuditModel, table=True):
    __tablename__ = "dms_attendance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    session_id: int = Field(foreign_key="dms_classsession.id")
    student_id: int = Field(foreign_key="dms_student.id")
    status: str = Field(default="present", max_length=20)
    remarks: str = Field(default="")
    
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_student_attendance"),
    )
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def get_status_display(self) -> str:
        return self.status.capitalize()

    session: ClassSession = Relationship(back_populates="attendance_records")

class DailyAttendance(AuditModel, table=True):
    __tablename__ = "dms_daily_attendance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    student_id: int = Field(foreign_key="dms_student.id")
    date: dt_date = Field(default_factory=dt_date.today, index=True)
    status: str = Field(default="present", max_length=20)
    remarks: str = Field(default="")
    
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_student_daily_attendance"),
    )
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def get_status_display(self) -> str:
        return self.status.capitalize()
