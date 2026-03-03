from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Integer, ForeignKey
from datetime import time
from app.models.base import AuditModel


if TYPE_CHECKING:
    from app.models.foundation import Institution, Course, Facility
    from app.models.people import Staff

class TimetableItem(AuditModel, table=True):
    __tablename__ = "dms_timetableitem"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    course_id: int = Field(foreign_key="dms_course.id")
    teacher_id: Optional[int] = Field(default=None, foreign_key="dms_staff.id")
    facility_id: Optional[int] = Field(default=None, foreign_key="dms_facility.id")
    
    day_of_week: str = Field(max_length=1)
    start_time: time = Field()
    end_time: time = Field()
    subject: str = Field(default="", max_length=200)
    is_active: bool = Field(default=True)
