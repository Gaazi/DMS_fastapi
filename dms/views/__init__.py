# dms/views/__init__.py
from ..logic.permissions import get_institution_with_access
from ..helper import resolve_currency_label, handle_manager_result
from .auth_views import *
from .base_views import *
from .student_views import *
from .staff_views import *
from .finance_views import *
from .audit_views import *
from .attendance_views import *
from .export_views import *
from .course_views import *
from .facility_views import *
from .inventory_views import *
from .schedule_views import *
from .finance_extra import *
from .public_admission_view import public_admission
