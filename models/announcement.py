from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, Relationship
from datetime import date, datetime
from .base import AuditModel
from .links import AnnouncementTargetParentLink

if TYPE_CHECKING:
    from .foundation import Institution
    from .people import Parent

class Announcement(AuditModel, table=True):
    __tablename__ = "dms_announcement"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    institution_id: int = Field(foreign_key="dms_institution.id")
    title: str = Field(max_length=255)
    content: str = Field()
    target_audience: str = Field(default="all", max_length=20)
    is_published: bool = Field(default=False)
    is_active: bool = Field(default=True)
    pinned: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expiry_date: Optional[date] = Field(default=None)

    target_parents: List["Parent"] = Relationship(link_model=AnnouncementTargetParentLink)
