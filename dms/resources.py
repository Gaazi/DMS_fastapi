from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import (
    Institution, Course, Facility,
    Student, Staff, Parent, Enrollment,
    ClassSession, Attendance, Staff_Attendance,
    Announcement,
    Fee, Fee_Payment, Donor, Income, Expense, WalletTransaction,
    Exam, ExamResult
)

class InstitutionResource(resources.ModelResource):
    class Meta:
        model = Institution
        fields = ('id', 'name', 'slug', 'type', 'address')

class ExamResource(resources.ModelResource):
    class Meta:
        model = Exam

class ExamResultResource(resources.ModelResource):
    class Meta:
        model = ExamResult

class CourseResource(resources.ModelResource):
    class Meta:
        model = Course

class FacilityResource(resources.ModelResource):
    class Meta:
        model = Facility

class StudentResource(resources.ModelResource):
    class Meta:
        model = Student

class StaffResource(resources.ModelResource):
    class Meta:
        model = Staff

class ParentResource(resources.ModelResource):
    class Meta:
        model = Parent

class EnrollmentResource(resources.ModelResource):
    class Meta:
        model = Enrollment

class ClassSessionResource(resources.ModelResource):
    class Meta:
        model = ClassSession

class AttendanceResource(resources.ModelResource):
    class Meta:
        model = Attendance

class StaffAttendanceResource(resources.ModelResource):
    class Meta:
        model = Staff_Attendance

class AnnouncementResource(resources.ModelResource):
    class Meta:
        model = Announcement

class FeeResource(resources.ModelResource):
    class Meta:
        model = Fee

class FeePaymentResource(resources.ModelResource):
    class Meta:
        model = Fee_Payment

class DonorResource(resources.ModelResource):
    class Meta:
        model = Donor

class IncomeResource(resources.ModelResource):
    class Meta:
        model = Income

class ExpenseResource(resources.ModelResource):
    class Meta:
        model = Expense

class WalletTransactionResource(resources.ModelResource):
    class Meta:
        model = WalletTransaction
