from sqladmin import Admin
from app.db.session import engine
from .core import InstitutionAdmin, CourseAdmin, FacilityAdmin, TimetableAdmin, ClassSessionAdmin
from .people import UserAdmin, StaffAdmin, ParentAdmin, StudentAdmin, AdmissionAdmin, StaffAttendanceAdmin, AttendanceAdmin, ActivityLogAdmin
from .finance import FeeAdmin, FeePaymentAdmin, WalletTransactionAdmin, DonorAdmin, IncomeAdmin, ExpenseAdmin, StaffAdvanceAdmin
from .inventory import ItemCategoryAdmin, InventoryItemAdmin, AssetIssueAdmin
from .system import AnnouncementAdmin, SystemSnapshotAdmin

def setup_admin(app):
    admin = Admin(app, engine)
    
    # Register Core Views
    admin.add_view(InstitutionAdmin)
    admin.add_view(CourseAdmin)
    admin.add_view(FacilityAdmin)
    admin.add_view(TimetableAdmin)
    admin.add_view(ClassSessionAdmin)
    
    # Register People Views
    admin.add_view(UserAdmin)
    admin.add_view(StaffAdmin)
    admin.add_view(ParentAdmin)
    admin.add_view(StudentAdmin)
    admin.add_view(AdmissionAdmin)
    admin.add_view(StaffAttendanceAdmin)
    admin.add_view(AttendanceAdmin)
    admin.add_view(ActivityLogAdmin)
    
    # Register Finance Views
    admin.add_view(FeeAdmin)
    admin.add_view(FeePaymentAdmin)
    admin.add_view(WalletTransactionAdmin)
    admin.add_view(DonorAdmin)
    admin.add_view(IncomeAdmin)
    admin.add_view(ExpenseAdmin)
    admin.add_view(StaffAdvanceAdmin)
    
    # Register Inventory Views
    admin.add_view(ItemCategoryAdmin)
    admin.add_view(InventoryItemAdmin)
    admin.add_view(AssetIssueAdmin)
    
    # Register System Views
    admin.add_view(AnnouncementAdmin)
    admin.add_view(SystemSnapshotAdmin)
    
    return admin
