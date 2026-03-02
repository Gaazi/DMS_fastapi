from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import date as dt_date, datetime
from .base import AuditModel

if TYPE_CHECKING:
    from .foundation import Institution, Course
    from .people import Student

class Exam(AuditModel, table=True):
    __tablename__ = "dms_exam"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="dms_institution.id")
    title: str = Field(max_length=200)
    term: str = Field(default="final_term", max_length=50)
    start_date: dt_date = Field()
    end_date: dt_date = Field()
    is_active: bool = Field(default=True)
    notes: str = Field(default="")

    results: List["ExamResult"] = Relationship(back_populates="exam")

class ExamResult(AuditModel, table=True):
    __tablename__ = "dms_examresult"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    exam_id: int = Field(foreign_key="dms_exam.id")
    student_id: int = Field(foreign_key="dms_student.id")
    course_id: int = Field(foreign_key="dms_course.id")
    
    total_marks: int = Field(default=100)
    obtained_marks: int = Field()
    teacher_remarks: str = Field(default="", max_length=255)
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    exam: Exam = Relationship(back_populates="results")
