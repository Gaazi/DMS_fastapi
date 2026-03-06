# app/api/__init__.py
from app.api.auth_api import router as auth_router
from app.api.base_api import router as base_router
from app.api.student_api import router as student_router
from app.api.staff_api import router as staff_router
from app.api.finance_api import router as finance_router
from app.api.audit_api import router as audit_router
from app.api.attendance_api import router as attendance_router
from app.api.export_api import router as export_router
from app.api.course_api import router as course_router
from app.api.facility_api import router as facility_router
from app.api.inventory_api import router as inventory_router
from app.api.schedule_api import router as schedule_router
from app.api.public_admission_api import router as public_admission_router
from app.api.exams_api import router as exams_router
from app.api.guardian_api import router as guardian_router
from app.api.global_api import router as global_router
from app.api.notification_api import router as notification_router
