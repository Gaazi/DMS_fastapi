from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import date as dt_date, datetime
from app.models.base import AuditModel
from decimal import Decimal
from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime

if TYPE_CHECKING:
    from app.models.foundation import Institution, Course
    from app.models.people import Student, Admission

class Fee(AuditModel, table=True):
    __tablename__ = "dms_fee"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    student_id: int = Field(foreign_key="dms_student.id")
    course_id: Optional[int] = Field(default=None, foreign_key="dms_course.id")
    admission_id: Optional[int] = Field(default=None, foreign_key="dms_enrollment.id")
    
    fee_type: str = Field(default="monthly", max_length=20)
    title: str = Field(default="", max_length=200)
    month: Optional[dt_date] = Field(default=None)
    
    amount_due: Decimal = Field(sa_column=Column(Float), default=0.0)
    amount_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    discount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    late_fee: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))
    
    due_date: Optional[dt_date] = Field(default=None)
    status: str = Field(default="Pending", max_length=20)
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    payments: List["Fee_Payment"] = Relationship(back_populates="fee")

class Fee_Payment(AuditModel, table=True):
    __tablename__ = "dms_fee_payment"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    student_id: int = Field(foreign_key="dms_student.id")
    fee_id: Optional[int] = Field(default=None, foreign_key="dms_fee.id")
    
    amount: Decimal = Field(sa_column=Column(Float))
    payment_date: datetime = Field(default_factory=datetime.utcnow)
    receipt_number: str = Field(max_length=50, unique=True, index=True)
    payment_method: str = Field(default="Cash", max_length=50)

    fee: Optional[Fee] = Relationship(back_populates="payments")
    wallet_entries: List["WalletTransaction"] = Relationship(back_populates="payment_ref")
    income_entry: Optional["Income"] = Relationship(back_populates="payment_record")

class WalletTransaction(AuditModel, table=True):
    __tablename__ = "dms_wallettransaction"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="dms_student.id")
    amount: Decimal = Field(sa_column=Column(Float))
    transaction_type: str = Field(max_length=10) # credit/debit
    payment_ref_id: Optional[int] = Field(default=None, foreign_key="dms_fee_payment.id")
    description: str = Field(default="", max_length=255)
    date: datetime = Field(default_factory=datetime.utcnow)

    payment_ref: Optional[Fee_Payment] = Relationship(back_populates="wallet_entries")

class Donor(AuditModel, table=True):
    __tablename__ = "dms_donor"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    name: str = Field(max_length=200)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=254)
    address: str = Field(default="")

    donations: List["Income"] = Relationship(back_populates="donor")

class Income(AuditModel, table=True):
    __tablename__ = "dms_income"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    payment_record_id: Optional[int] = Field(default=None, foreign_key="dms_fee_payment.id")
    donor_id: Optional[int] = Field(default=None, foreign_key="dms_donor.id")
    source: str = Field(default="Donation", max_length=50)
    amount: Decimal = Field(sa_column=Column(Float))
    date: dt_date = Field(default_factory=dt_date.today)
    description: str = Field(default="")
    receipt_number: Optional[str] = Field(default=None, max_length=50)

    payment_record: Optional[Fee_Payment] = Relationship(back_populates="income_entry")
    donor: Optional[Donor] = Relationship(back_populates="donations")

class Expense(AuditModel, table=True):
    __tablename__ = "dms_expense"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    amount: Decimal = Field(sa_column=Column(Float))
    category: str = Field(max_length=50)
    description: str = Field(default="")
    date: dt_date = Field(default_factory=dt_date.today)
    receipt_number: Optional[str] = Field(default=None, max_length=50)
