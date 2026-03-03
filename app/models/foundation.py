from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Integer, ForeignKey
from datetime import date
from app.models.base import AuditModel
from app.models.links import CourseStaffLink


if TYPE_CHECKING:
    from app.models.people import Staff, Admission

class Institution(AuditModel, table=True):
    __tablename__ = "dms_institution"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="auth_user.id")
    reg_id: Optional[str] = Field(default=None, index=True, max_length=20)
    name: str = Field(max_length=50)
    name_in_urdu: Optional[str] = Field(default=None, max_length=200)
    slug: Optional[str] = Field(default=None, index=True, max_length=255)
    type: str = Field(max_length=20)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)
    address: str = Field(default="")
    logo: Optional[str] = Field(default=None, max_length=100)
    is_approved: bool = Field(default=False)
    active_date: Optional[date] = Field(default=None)
    status: str = Field(default="active", max_length=20)
    is_default: bool = Field(default=False)

    # Relationships
    courses: List["Course"] = Relationship(back_populates="institution")
    facilities: List["Facility"] = Relationship(back_populates="institution")

class Course(AuditModel, table=True):
    __tablename__ = "dms_course"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    title: str = Field(max_length=200)
    category: str = Field(max_length=50)
    description: str = Field(default="")
    fee_type: str = Field(default="monthly", max_length=20)
    admission_fee: float = Field(default=0.0)
    course_fee: float = Field(default=0.0)
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)

    def get_category_display(self) -> str:
        cat_map = {
            "academic": "تعلیمی (Academic)",
            "general": "تکنیکی/عام (General)",
            "special": "خصوصی (Special)",
            "masjid": "مسجد/نماز",
            "dars": "درسِ نظامی / عالم کورس",
            "hifz": "حفظِ قرآن",
            "nazra": "ناظرہ قرآن",
            "other": "دیگر"
        }
        return cat_map.get(self.category.lower(), self.category.capitalize())

    def get_fee_type_display(self) -> str:
        type_map = {
            "monthly": "ماہانہ",
            "yearly": "سالانہ",
            "one_time": "ایک بار",
            "onetime": "ایک بار",
            "none": "مفت",
            "free": "مفت"
        }
        return type_map.get(self.fee_type.lower(), self.fee_type.capitalize())

    # Relationships
    institution: Institution = Relationship(back_populates="courses")
    instructors: List["Staff"] = Relationship(back_populates="courses_taught", link_model=CourseStaffLink)
    admissions: List["Admission"] = Relationship(back_populates="course")

    @property
    def student_count(self) -> int:
        """کل فعال طلبہ کی تعداد۔"""
        return len([a for a in self.admissions if a.status == 'active'])

class Facility(AuditModel, table=True):
    __tablename__ = "dms_facility"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    name: str = Field(max_length=200)
    facility_type: str = Field(max_length=50)
    is_available: bool = Field(default=True)

    # Relationships
    institution: Institution = Relationship(back_populates="facilities")
