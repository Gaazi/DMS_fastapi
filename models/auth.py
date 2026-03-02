from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "auth_user"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    password: str = Field(max_length=128)
    last_login: Optional[datetime] = Field(default=None)
    is_superuser: bool = Field(default=False)
    username: str = Field(max_length=150, unique=True, index=True)
    first_name: str = Field(max_length=150, default="")
    last_name: str = Field(max_length=150, default="")
    email: str = Field(max_length=254, default="")
    is_staff: bool = Field(default=False)
    is_active: bool = Field(default=True)
    date_joined: datetime = Field(default_factory=datetime.utcnow)
