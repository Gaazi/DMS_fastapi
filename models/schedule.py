from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import time
from .audit_model import AuditModel

if TYPE_CHECKING:
    from .foundation import Institution, Course, Facility
    from .people import Staff

class TimetableItem(AuditModel, table=True):
    __tablename__ = "dms_timetableitem"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="dms_institution.id")
    course_id: int = Field(foreign_key="dms_course.id")
    teacher_id: Optional[int] = Field(default=None, foreign_key="dms_staff.id")
    facility_id: Optional[int] = Field(default=None, foreign_key="dms_facility.id")
    
    day_of_week: str = Field(max_length=1)
    start_time: time = Field()
    end_time: time = Field()
    subject: str = Field(default="", max_length=200)
    is_active: bool = Field(default=True)
