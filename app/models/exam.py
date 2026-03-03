from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import date as dt_date, datetime
from app.models.base import AuditModel
from sqlalchemy import Column, Integer, ForeignKey

if TYPE_CHECKING:
    from app.models.foundation import Institution, Course
    from app.models.people import Student

class Exam(AuditModel, table=True):
    __tablename__ = "dms_exam"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
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

    @property
    def percentage(self) -> float:
        """حاصل کردہ نمبروں کا فیصد۔"""
        if self.total_marks > 0:
            return round((self.obtained_marks / self.total_marks) * 100, 2)
        return 0.0

    @property
    def grade(self) -> str:
        """فیصد کی بنیاد پر گریڈ کا تعین۔"""
        p = self.percentage
        if p >= 90: return "A+"
        if p >= 80: return "A"
        if p >= 70: return "B"
        if p >= 60: return "C"
        if p >= 50: return "D"
        if p >= 40: return "E"
        return "F"

