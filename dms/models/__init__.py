# dms/models/__init__.py

# تمام فائلوں کے نئے ناموں کے ساتھ امپورٹ
from .foundation_model import Institution, Course, Facility
from .people_model import Student, Staff, Parent, Enrollment
from .attendance_model import ClassSession, Attendance, Staff_Attendance
from .exam_model import Exam, ExamResult
from .announcement_model import Announcement
from .finance_model import Fee, Fee_Payment, Donor, Income, Expense, WalletTransaction
from .audit_model import AuditModel
from .backup_model import SystemSnapshot
from .inventory_model import ItemCategory, InventoryItem, AssetIssue
from .schedule_model import TimetableItem

# ڈینگو کو بتانا کہ یہ تمام ماڈلز دستیاب ہیں
__all__ = [
    'Institution', 'Course', 'Facility',
    'Student', 'Staff', 'Parent', 'Enrollment',
    'ClassSession', 'Attendance', 'Staff_Attendance',
    'Exam', 'ExamResult',
    'Announcement',
    'Fee', 'Fee_Payment', 'Donor', 'Income', 'Expense', 'WalletTransaction',
    'SystemSnapshot',
    'ItemCategory', 'InventoryItem', 'AssetIssue',
    'TimetableItem'
]