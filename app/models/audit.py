from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from .base import AuditModel

if TYPE_CHECKING:
    from .auth import User

class ActivityLog(SQLModel, table=True):
    __tablename__ = "dms_activitylog"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    inst_id: int = Field(foreign_key="dms_institution.id", alias="institution_id")
    user_id: Optional[int] = Field(default=None, foreign_key="auth_user.id")
    
    action: str = Field(max_length=20) # create, update, delete, restore, hard_delete
    model_name: str = Field(max_length=50)
    object_id: int
    object_repr: str = Field(max_length=255)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    changes: Optional[str] = Field(default=None) # JSON data of changes

    # Relationships
    user: Optional["User"] = Relationship()
