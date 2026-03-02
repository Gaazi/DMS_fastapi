from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Float
from datetime import date, time, datetime
from .base import AuditModel
from decimal import Decimal
from .links import StudentParentLink, CourseStaffLink

if TYPE_CHECKING:
    from .foundation import Institution, Course

class PersonBase(AuditModel):
    institution_id: int = Field(foreign_key="dms_institution.id")
    user_id: Optional[int] = Field(default=None, foreign_key="auth_user.id")
    reg_id: Optional[str] = Field(default=None, max_length=20, index=True)
    name: str = Field(max_length=200)
    father_name: Optional[str] = Field(default=None, max_length=200)
    gender: str = Field(default="male", max_length=10)
    mobile: Optional[str] = Field(default=None, max_length=20)
    mobile2: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=254)
    address: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)

class Staff(PersonBase, table=True):
    __tablename__ = "dms_staff"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    role: str = Field(default="teacher", max_length=50)
    photo: Optional[str] = Field(default=None, max_length=100)
    base_salary: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    hire_date: Optional[date] = Field(default=None)
    shift_start: Optional[time] = Field(default=None)
    shift_end: Optional[time] = Field(default=None)
    current_advance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    notes: str = Field(default="")
    
    courses_taught: List["Course"] = Relationship(back_populates="instructors", link_model=CourseStaffLink)

class Parent(PersonBase, table=True):
    __tablename__ = "dms_parent"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    relationship: str = Field(default="guardian", max_length=20)
    
    students: List["Student"] = Relationship(back_populates="parents", link_model=StudentParentLink)

class Student(PersonBase, table=True):
    __tablename__ = "dms_student"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: Optional[str] = Field(default=None, max_length=255)
    photo: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[date] = Field(default=None)
    blood_group: Optional[str] = Field(default=None, max_length=5)
    guardian_name: str = Field(default="", max_length=200)
    guardian_relation: str = Field(default="", max_length=100)
    notes: str = Field(default="")
    wallet_balance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    enrollment_date: date = Field(default_factory=date.today)

    parents: List[Parent] = Relationship(back_populates="students", link_model=StudentParentLink)
    enrollments: List["Enrollment"] = Relationship(back_populates="student")

class Enrollment(AuditModel, table=True):
    __tablename__ = "dms_enrollment"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="dms_student.id")
    course_id: int = Field(foreign_key="dms_course.id")
    enrollment_date: date = Field(default_factory=date.today)
    roll_no: Optional[str] = Field(default=None, max_length=50)
    admission_fee_discount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    agreed_admission_fee: Optional[Decimal] = Field(default=None, sa_column=Column(Float))
    course_fee_discount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    agreed_course_fee: Optional[Decimal] = Field(default=None, sa_column=Column(Float))
    fee_start_month: Optional[date] = Field(default=None)
    fee_type_override: Optional[str] = Field(default=None, max_length=20)
    status: str = Field(default="active", max_length=20)

    student: Student = Relationship(back_populates="enrollments")

class StaffAdvance(SQLModel, table=True):
    __tablename__ = "dms_staffadvance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="dms_staff.id")
    amount: Decimal = Field(sa_column=Column(Float))
    date: date = Field(default_factory=date.today)
    is_adjusted: bool = Field(default=False)
