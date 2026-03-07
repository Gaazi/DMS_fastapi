from app.admin.base import DMSModelView
from app.models.auth import User
from app.models.people import Staff, Parent, Student, Admission
from app.models.attendance import Attendance, Staff_Attendance
from app.models.audit import ActivityLog
from starlette.requests import Request

class UserAdmin(DMSModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_superuser, User.is_active, "reset_password"]
    column_searchable_list = [User.username, User.email]
    form_include_pk = False
    category = "People"
    icon = "fa-solid fa-users-gear"
    name_plural = "Users"
    column_labels = {"reset_password": "پاس ورڈ"}

    # ہر row میں Reset Password کا لنک دکھائیں
    column_formatters = {
        "reset_password": lambda m, a: f'<a href="/admin/reset-password/{m.id}" '
                                       f'style="background:#1d4ed8;color:#fff;padding:4px 10px;'
                                       f'border-radius:6px;text-decoration:none;font-size:12px;">'
                                       f'🔑 Reset</a>'
    }

    async def on_model_change(self, data: dict, model: User, is_created: bool, request: Request) -> None:
        """
        اگر admin نے password فیلڈ بھری ہے تو اسے hash کر دیں۔
        اگر فیلڈ خالی چھوڑی تو پرانا password رہنے دیں۔
        """
        new_password = data.get("password", "").strip()
        if new_password:
            from app.logic.auth import pwd_context
            data["password"] = pwd_context.hash(new_password)
        elif not is_created and model.password:
            # خالی ہے اور یہ edit ہے تو پرانا رکھیں
            data["password"] = model.password

class StaffAdmin(DMSModelView, model=Staff):
    column_list = [Staff.id, Staff.name, Staff.reg_id, Staff.mobile, Staff.role]
    column_searchable_list = [Staff.name, Staff.reg_id, Staff.mobile]
    category = "People"
    icon = "fa-solid fa-user-tie"

class ParentAdmin(DMSModelView, model=Parent):
    column_list = [Parent.id, Parent.name, Parent.mobile, Parent.reg_id]
    column_searchable_list = [Parent.name, Parent.mobile, Parent.reg_id]
    category = "People"
    icon = "fa-solid fa-user-group"

class StudentAdmin(DMSModelView, model=Student):
    column_list = [Student.id, Student.name, Student.reg_id, Student.mobile, Student.admission_date]
    column_searchable_list = [Student.name, Student.reg_id, Student.mobile]
    category = "People"
    icon = "fa-solid fa-user-graduate"

class AdmissionAdmin(DMSModelView, model=Admission):
    column_list = [Admission.id, Admission.student_id, Admission.course_id, Admission.status, Admission.admission_date]
    category = "People"
    icon = "fa-solid fa-id-card"

class StaffAttendanceAdmin(DMSModelView, model=Staff_Attendance):
    column_list = [Staff_Attendance.id, Staff_Attendance.staff_member_id, Staff_Attendance.date, Staff_Attendance.status]
    category = "Attendance"
    icon = "fa-solid fa-user-check"

class AttendanceAdmin(DMSModelView, model=Attendance):
    column_list = [Attendance.id, Attendance.student_id, Attendance.session_id, Attendance.status, Attendance.inst_id]
    category = "Attendance"
    icon = "fa-solid fa-clipboard-user"

class ActivityLogAdmin(DMSModelView, model=ActivityLog):
    column_list = [ActivityLog.id, ActivityLog.user_id, ActivityLog.action, ActivityLog.model_name, ActivityLog.timestamp]
    category = "Audit"
    icon = "fa-solid fa-gears"
