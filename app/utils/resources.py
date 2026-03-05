import tablib
from typing import List, Optional
from app.models import (
    Attendance,
    ClassSession,
    Donor,
    Enrollment,
    Expense,
    Facility,
    Income,
    Institution,
    Course,
    Staff,
    Staff_Attendance,
    Student,
    Fee,
    Fee_Payment,
    Parent,
    Announcement,
    WalletTransaction,
    Exam,
    ExamResult
)

class ModelResource:
    """
    A standalone replacement for django-import-export's ModelResource 
    that works with SQLModel/SQLAlchemy objects.
    """
    model = None
    fields: Optional[List[str]] = None

    def __init__(self):
        # Extract fields from model metadata if not provided
        if self.model and not self.fields:
            self.fields = [c.key for c in self.model.__table__.columns]

    def export(self, queryset):
        """Export from a SQLModel queryset (result of session.exec)."""
        dataset = tablib.Dataset()
        headers = self.fields if self.fields else [c.key for c in self.model.__table__.columns]
        dataset.headers = headers
        
        for obj in queryset:
            row = []
            for field in headers:
                val = getattr(obj, field, "")
                # Serialize dates/times for export
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                row.append(val)
            dataset.append(row)
        return dataset

    def import_data(self, dataset, session, dry_run=False, raise_errors=False):
        """Simple implementation of data import."""
        # result object to match django-import-export structure
        class Result:
            def __init__(self): self.totals = {'new': 0, 'update': 0, 'skip': 0, 'error': 0}
        
        result = Result()
        if not session: return result
        
        for row_dict in dataset.dict:
            try:
                # Basic create-or-update logic
                obj_id = row_dict.get('id')
                if obj_id:
                    existing = session.get(self.model, obj_id)
                    if existing:
                        for k, v in row_dict.items():
                            setattr(existing, k, v)
                        result.totals['update'] += 1
                        continue
                
                # Create new
                new_obj = self.model(**row_dict)
                session.add(new_obj)
                result.totals['new'] += 1
            except Exception as e:
                result.totals['error'] += 1
                if raise_errors: raise e
        
        if not dry_run:
            session.commit()
            
        return result

class InstitutionResource(ModelResource):
    model = Institution
    fields = ['id', 'name', 'slug', 'type', 'address']

class ExamResource(ModelResource):
    model = Exam

class ExamResultResource(ModelResource):
    model = ExamResult

class CourseResource(ModelResource):
    model = Course

class FacilityResource(ModelResource):
    model = Facility

class StudentResource(ModelResource):
    model = Student

class StaffResource(ModelResource):
    model = Staff

class ParentResource(ModelResource):
    model = Parent

class EnrollmentResource(ModelResource):
    model = Enrollment

class ClassSessionResource(ModelResource):
    model = ClassSession

class AttendanceResource(ModelResource):
    model = Attendance

class StaffAttendanceResource(ModelResource):
    model = Staff_Attendance

class AnnouncementResource(ModelResource):
    model = Announcement

class FeeResource(ModelResource):
    model = Fee

class FeePaymentResource(ModelResource):
    model = Fee_Payment

class DonorResource(ModelResource):
    model = Donor

class IncomeResource(ModelResource):
    model = Income

class ExpenseResource(ModelResource):
    model = Expense

class WalletTransactionResource(ModelResource):
    model = WalletTransaction
