from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship, Column, Float
from datetime import date as dt_date
from .base import AuditModel
from decimal import Decimal
from sqlalchemy import Column, Integer, ForeignKey

if TYPE_CHECKING:
    from .foundation import Institution
    from .people import Student, Staff

class ItemCategory(AuditModel, table=True):
    __tablename__ = "dms_itemcategory"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    name: str = Field(max_length=100)
    description: str = Field(default="")

class InventoryItem(AuditModel, table=True):
    __tablename__ = "dms_inventoryitem"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(sa_column=Column("institution_id", Integer, ForeignKey("dms_institution.id")))
    category_id: Optional[int] = Field(default=None, foreign_key="dms_itemcategory.id")
    name: str = Field(max_length=255)
    item_type: str = Field(default="book", max_length=20)
    author: str = Field(default="", max_length=255)
    isbn: str = Field(default="", max_length=50)
    total_quantity: int = Field(default=0)
    available_quantity: int = Field(default=0)
    location: str = Field(default="", max_length=100)
    price: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Float))

class AssetIssue(AuditModel, table=True):
    __tablename__ = "dms_assetissue"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="dms_inventoryitem.id")
    student_id: Optional[int] = Field(default=None, foreign_key="dms_student.id")
    staff_id: Optional[int] = Field(default=None, foreign_key="dms_staff.id")
    quantity: int = Field(default=1)
    issue_date: dt_date = Field(default_factory=dt_date.today)
    due_date: Optional[dt_date] = Field(default=None)
    return_date: Optional[dt_date] = Field(default=None)
    is_returned: bool = Field(default=False)
    notes: str = Field(default="")
