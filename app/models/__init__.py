# Models package for DMS FastAPI
from app.models.auth import User
from app.models.links import CourseStaffLink, StudentParentLink, AnnouncementTargetParentLink
from app.models.foundation import Institution, Course, Facility
from app.models.people import Staff, Parent, Student, Admission, StaffAdvance
from app.models.finance import Fee, Fee_Payment, WalletTransaction, Donor, Income, Expense
from app.models.attendance import ClassSession, Staff_Attendance, Attendance
from app.models.exam import Exam, ExamResult
from app.models.announcement import Announcement
from app.models.inventory import ItemCategory, InventoryItem, AssetIssue
from app.models.schedule import TimetableItem
from app.models.backup import SystemSnapshot
from app.models.audit import ActivityLog

__all__ = [
    'User',
    'Institution', 'Course', 'Facility',
    'Staff', 'Parent', 'Student', 'Admission', 'Enrollment', 'StaffAdvance',
    'Fee', 'Fee_Payment', 'WalletTransaction', 'Donor', 'Income', 'Expense',
    'ClassSession', 'Staff_Attendance', 'Attendance',
    'Exam', 'ExamResult',
    'Announcement',
    'ItemCategory', 'InventoryItem', 'AssetIssue',
    'TimetableItem',
    'SystemSnapshot',
    'ActivityLog'
]

Enrollment = Admission

