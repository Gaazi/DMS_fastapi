# app/api/__init__.py
from .auth_api import router as auth_router
from .base_api import router as base_router
from .student_api import router as student_router
from .staff_api import router as staff_router
from .finance_api import router as finance_router
from .audit_api import router as audit_router
from .attendance_api import router as attendance_router
from .export_api import router as export_router
from .course_api import router as course_router
from .facility_api import router as facility_router
from .inventory_api import router as inventory_router
from .schedule_api import router as schedule_router
from .finance_extra_api import router as finance_extra_router
from .public_admission_api import router as public_admission_router
from .exams_api import router as exams_router
from .guardian_api import router as guardian_router
from .global_api import router as global_router
