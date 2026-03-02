# Models package for DMS FastAPI
from .auth import User
from .links import CourseStaffLink, StudentParentLink, AnnouncementTargetParentLink
from .foundation import Institution, Course, Facility
from .people import Staff, Parent, Student, Enrollment, StaffAdvance
from .finance import Fee, Fee_Payment, WalletTransaction, Donor, Income, Expense
from .attendance import ClassSession, Staff_Attendance, Attendance
from .exam import Exam, ExamResult
from .announcement import Announcement
from .inventory import ItemCategory, InventoryItem, AssetIssue
from .schedule import TimetableItem

__all__ = [
    'User',
    'Institution', 'Course', 'Facility',
    'Staff', 'Parent', 'Student', 'Enrollment', 'StaffAdvance',
    'Fee', 'Fee_Payment', 'WalletTransaction', 'Donor', 'Income', 'Expense',
    'ClassSession', 'Staff_Attendance', 'Attendance',
    'Exam', 'ExamResult',
    'Announcement',
    'ItemCategory', 'InventoryItem', 'AssetIssue',
    'TimetableItem'
]
