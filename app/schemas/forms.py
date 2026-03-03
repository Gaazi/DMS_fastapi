
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from decimal import Decimal
from datetime import date, time

class FormError(BaseModel):
    field: str
    message: str

class BaseFormSchema(BaseModel):
    def get_errors(self) -> dict:
        # Helper to convert pydantic errors to a simpler dict for templates
        # Note: This is a basic version, usually we catch ValidationError
        return {}

class IncomeFormSchema(BaseModel):
    donor_id: Optional[int] = None
    new_donor_name: Optional[str] = None
    new_donor_phone: Optional[str] = None
    new_donor_email: Optional[str] = None
    new_donor_address: Optional[str] = None
    
    amount: Decimal = Field(gt=0, description="رقم 0 سے زیادہ ہونی چاہیے")
    source: str = Field(min_length=2, description="ذریعہ درج کریں")
    date: date
    description: Optional[str] = ""

    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('رقم 0 سے زیادہ ہونی چاہیے۔')
        return v

class ExpenseFormSchema(BaseModel):
    amount: Decimal = Field(gt=0)
    category: str
    date: date
    description: Optional[str] = ""

    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('رقم 0 سے زیادہ ہونی چاہیے۔')
        return v

class LoginFormSchema(BaseModel):
    username: str = Field(min_length=3, description="نام کم از کم 3 حروف کا ہونا چاہیے")
    password: str = Field(min_length=6, description="پاس ورڈ کم از کم 6 حروف کا ہونا چاہیے")

class SignupFormSchema(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field(min_length=6)

class StudentAdmissionSchema(BaseModel):
    name: str = Field(min_length=2, description="نام درج کریں")
    father_name: Optional[str] = ""
    guardian_name: Optional[str] = ""
    guardian_relation: Optional[str] = "father"
    mobile: Optional[str] = ""
    mobile2: Optional[str] = ""
    gender: str = "male"
    date_of_birth: Optional[date] = None

    @validator('date_of_birth', pre=True)
    def parse_dob(cls, v):
        if v == "" or v is None:
            return None
        return v
    email: Optional[str] = ""
    blood_group: Optional[str] = ""
    fee_start_month: Optional[str] = ""
    
    @validator('fee_start_month', pre=True)
    def empty_month_to_none(cls, v):
        if v == "" or v is None:
            return ""
        return v
    address: Optional[str] = ""
    
    # Course fields
    course_id: Optional[int] = None
    agreed_course_fee: Decimal = 0
    agreed_admission_fee: Decimal = 0
    initial_payment: Decimal = 0
    payment_method: str = "Cash"
    custom_fee_type: str = "regular"
    notes: Optional[str] = ""
    
    @validator('course_id', pre=True)
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError('درست انتخاب کریں (Invalid Selection)')

    @validator('agreed_course_fee', 'agreed_admission_fee', 'initial_payment', pre=True)
    def empty_string_to_zero(cls, v):
        if v == "" or v is None:
            return 0
        try:
            return Decimal(str(v))
        except (ValueError, TypeError):
            raise ValueError('درست رقم درج کریں (Invalid Amount)')



class PublicAdmissionSchema(BaseModel):
    name: str = Field(min_length=2, description="پورا نام درج کریں")
    father_name: str = Field(min_length=2, description="والد کا نام درج کریں")
    mobile: str = Field(min_length=10, description="درست فون نمبر دیں")
    address: str = Field(min_length=5, description="پتہ درج کریں")
    course_id: Optional[int] = None

    @validator('course_id', pre=True)
    def empty_string_to_none(cls, v):
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError('درست انتخاب کریں (Invalid Selection)')

class StaffFormSchema(BaseModel):
    name: str = Field(min_length=2, description="نام درج کریں")
    father_name: Optional[str] = ""
    mobile: str = Field(min_length=10, description="درست فون نمبر درج کریں")
    email: Optional[EmailStr] = None
    role: str = "teacher"
    base_salary: Decimal = 0
    hire_date: date
    shift_start: Optional[time] = None
    shift_end: Optional[time] = None
    address: Optional[str] = ""
    is_active: bool = True

class CourseFormSchema(BaseModel):
    id: Optional[int] = None
    title: str = Field(min_length=2, description="کورس کا عنوان درج کریں")
    category: str = "academic"
    fee_type: str = "monthly"
    admission_fee: float = 0
    course_fee: float = 0
    description: Optional[str] = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    capacity: Optional[int] = None
    is_active: bool = True
    
    @validator("is_active", pre=True)
    def handle_checkbox(cls, v):
        if v in (True, "true", "on", "1"): return True
        return False

class DonorFormSchema(BaseModel):
    name: str = Field(min_length=2, description="نام درج کریں")
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = ""

class InstitutionSettingsSchema(BaseModel):
    name: str = Field(min_length=3, description="ادارے کا نام درج کریں")
    name_in_urdu: Optional[str] = ""
    institution_type: str = "madrasa"
    phone: Optional[str] = ""
    email: Optional[EmailStr] = None
    address: Optional[str] = ""
    logo_url: Optional[str] = None
    theme_color: str = "#10b981"

class SetupInstitutionSchema(BaseModel):
    name: str = Field(min_length=3, description="ادارے کا نام درج کریں")
    slug: Optional[str] = None
    type: str = "school"

class ExamFormSchema(BaseModel):
    title: str = Field(min_length=2, description="امتحان کا عنوان درج کریں")
    date: date

class InventoryItemSchema(BaseModel):
    name: str = Field(min_length=2, description="آئٹم کا نام درج کریں")
    category: str = "General"
    quantity: int = Field(default=0, ge=0)
    price: Decimal = 0
    description: Optional[str] = ""

class InventoryIssueSchema(BaseModel):
    item_id: int
    student_id: Optional[int] = None
    staff_id: Optional[int] = None
    quantity: int = Field(default=1, gt=0)
    due_date: Optional[date] = None

class FacilityFormSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(min_length=2, description="سہولت کا نام درج کریں")
    type: str = "other"
    capacity: Optional[int] = 0
    description: Optional[str] = ""

class PublicDonationSchema(BaseModel):
    donor_name: str = Field(min_length=2, description="پورا نام درج کریں")
    donor_phone: Optional[str] = None
    amount: Decimal = Field(gt=0, description="درست رقم درج کریں")
    notes: Optional[str] = ""

class StaffAdvanceSchema(BaseModel):
    staff_id: int
    amount: Decimal = Field(gt=0, description="رقم 0 سے زیادہ ہونی چاہیے")
    date: date

class StaffPayrollSchema(BaseModel):
    staff_id: int
    amount: Decimal = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int
