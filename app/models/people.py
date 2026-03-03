from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Float
from datetime import date as dt_date, time, datetime
from .base import AuditModel
from decimal import Decimal
from .links import StudentParentLink, CourseStaffLink
from sqlalchemy import Column, Integer, ForeignKey, Float

if TYPE_CHECKING:
    from .foundation import Institution, Course
    from .auth import User

class Person(AuditModel):
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
    
    @property
    def full_name(self) -> str:
        return self.name


class Staff(Person, table=True):
    __tablename__ = "dms_staff"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    role: str = Field(default="teacher", max_length=50)
    photo: Optional[str] = Field(default=None, max_length=100)
    base_salary: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    hire_date: Optional[dt_date] = Field(default=None)
    shift_start: Optional[time] = Field(default=None)
    shift_end: Optional[time] = Field(default=None)
    current_advance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    notes: str = Field(default="")
    
    courses_taught: List["Course"] = Relationship(back_populates="instructors", link_model=CourseStaffLink)
    user: Optional["User"] = Relationship(back_populates="staff")

class Parent(Person, table=True):
    __tablename__ = "dms_parent"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    relationship: str = Field(default="guardian", max_length=20)
    
    students: List["Student"] = Relationship(back_populates="parents", link_model=StudentParentLink)

class Student(Person, table=True):
    __tablename__ = "dms_student"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    slug: Optional[str] = Field(default=None, max_length=255)
    photo: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[dt_date] = Field(default=None)
    blood_group: Optional[str] = Field(default=None, max_length=5)
    guardian_name: str = Field(default="", max_length=200)
    guardian_relation: str = Field(default="", max_length=100)
    notes: str = Field(default="")
    wallet_balance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    admission_date: dt_date = Field(sa_column=Column("enrollment_date", Float)) # Map to existing DB column

    parents: List[Parent] = Relationship(back_populates="students", link_model=StudentParentLink)
    admissions: List["Admission"] = Relationship(back_populates="student")

    # Extra properties for template compatibility (Calculated in routes)
    @property
    def month_presents(self) -> int:
        return getattr(self, "_month_presents", 0)
    
    @month_presents.setter
    def month_presents(self, value):
        self._month_presents = value

    @property
    def month_absents(self) -> int:
        return getattr(self, "_month_absents", 0)
    
    @month_absents.setter
    def month_absents(self, value):
        self._month_absents = value

    @property
    def has_pending_fee(self) -> bool:
        return getattr(self, "_has_pending_fee", False)
    
    @has_pending_fee.setter
    def has_pending_fee(self, value):
        self._has_pending_fee = value

    @property
    def month_due_amount(self) -> Decimal:
        return getattr(self, "_month_due_amount", Decimal("0.00"))
    
    @month_due_amount.setter
    def month_due_amount(self, value):
        self._month_due_amount = value

class Admission(AuditModel, table=True):
    __tablename__ = "dms_enrollment" # Keeping original table name for data safety
    
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="dms_student.id")
    course_id: int = Field(foreign_key="dms_course.id")
    admission_date: dt_date = Field(sa_column=Column("enrollment_date", Float)) # Map to existing DB column
    roll_no: Optional[str] = Field(default=None, max_length=50)
    admission_fee_discount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    agreed_admission_fee: Optional[Decimal] = Field(default=None, sa_column=Column(Float))
    course_fee_discount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    agreed_course_fee: Optional[Decimal] = Field(default=None, sa_column=Column(Float))
    fee_start_month: Optional[dt_date] = Field(default=None)
    fee_type_override: Optional[str] = Field(default=None, max_length=20)
    status: str = Field(default="active", max_length=20)

    student: Student = Relationship(back_populates="admissions")

class StaffAdvance(SQLModel, table=True):
    __tablename__ = "dms_staffadvance"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    staff_id: int = Field(foreign_key="dms_staff.id")
    amount: Decimal = Field(sa_column=Column(Float))
    date: dt_date = Field(default_factory=dt_date.today)
    is_adjusted: bool = Field(default=False)
