from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, DateTime

class AuditModel(SQLModel):
    # created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    # updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    created_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True)
    )
    
    # deleted_at for SafeDelete simulation
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
