from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from app.models.base import AuditModel

if TYPE_CHECKING:
    from app.models.foundation import Institution

class SystemSnapshot(SQLModel, table=True):
    __tablename__ = "dms_backup" # Keeping original table name for data safety
    
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str = Field(max_length=255)
    file: str = Field(max_length=100) # FileField in Django
    institution_id: Optional[int] = Field(default=None, foreign_key="dms_institution.id")
    backup_type: str = Field(default="manual", max_length=20)
    size: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(default=None)
