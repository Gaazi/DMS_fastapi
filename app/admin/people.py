from sqladmin import ModelView
from app.models.auth import User
from app.models.people import Staff, Parent, Student, Admission
from app.models.attendance import Attendance, Staff_Attendance
from app.models.audit import ActivityLog

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.email, User.is_superuser, User.is_active]
    column_searchable_list = [User.username, User.email]
    category = "People"
    icon = "fa-solid fa-users-gear"

class StaffAdmin(ModelView, model=Staff):
    column_list = [Staff.id, Staff.full_name, Staff.reg_id, Staff.phone, Staff.roles]
    column_searchable_list = [Staff.full_name, Staff.reg_id, Staff.phone]
    category = "People"
    icon = "fa-solid fa-user-tie"

class ParentAdmin(ModelView, model=Parent):
    column_list = [Parent.id, Parent.full_name, Parent.phone, Parent.reg_id]
    column_searchable_list = [Parent.full_name, Parent.phone, Parent.reg_id]
    category = "People"
    icon = "fa-solid fa-user-group"

class StudentAdmin(ModelView, model=Student):
    column_list = [Student.id, Student.full_name, Student.reg_id, Student.phone, Student.admission_date]
    column_searchable_list = [Student.full_name, Student.reg_id, Student.phone]
    category = "People"
    icon = "fa-solid fa-user-graduate"

class AdmissionAdmin(ModelView, model=Admission):
    column_list = [Admission.id, Admission.student_id, Admission.course_id, Admission.status, Admission.admission_date]
    category = "People"
    icon = "fa-solid fa-id-card"

class StaffAttendanceAdmin(ModelView, model=Staff_Attendance):
    column_list = [Staff_Attendance.id, Staff_Attendance.staff_member_id, Staff_Attendance.date, Staff_Attendance.status]
    category = "Attendance"
    icon = "fa-solid fa-user-check"

class AttendanceAdmin(ModelView, model=Attendance):
    column_list = [Attendance.id, Attendance.student_id, Attendance.session_id, Attendance.status, Attendance.inst_id]
    category = "Attendance"
    icon = "fa-solid fa-clipboard-user"

class ActivityLogAdmin(ModelView, model=ActivityLog):
    column_list = [ActivityLog.id, ActivityLog.user_id, ActivityLog.action, ActivityLog.model_name, ActivityLog.timestamp]
    category = "Audit"
    icon = "fa-solid fa-gears"
