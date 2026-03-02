from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime

class StudentBase(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    course_id: Optional[int] = None

class StudentCreate(StudentBase):
    pass

class StudentRead(StudentBase):
    id: int
    reg_id: str
    status: str

    class Config:
        orm_mode = True

class StaffBase(BaseModel):
    name: str
    phone: str
    role: str

class StaffCreate(StaffBase):
    pass

class StaffRead(StaffBase):
    id: int
    
    class Config:
        orm_mode = True
