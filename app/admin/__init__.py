from sqladmin import Admin, ModelView
from app.db.session import engine
from app.admin.auth import AdminAuth

# Core
from app.admin.core import (
    InstitutionAdmin, CourseAdmin, FacilityAdmin,
    TimetableAdmin, ClassSessionAdmin
)
# People
from app.admin.people import (
    UserAdmin, StaffAdmin, ParentAdmin, StudentAdmin,
    AdmissionAdmin, StaffAttendanceAdmin, AttendanceAdmin, ActivityLogAdmin
)
# Finance
from app.admin.finance import (
    FeeAdmin, FeePaymentAdmin, WalletTransactionAdmin,
    DonorAdmin, IncomeAdmin, ExpenseAdmin, StaffAdvanceAdmin
)
# Inventory
from app.admin.inventory import (
    ItemCategoryAdmin, InventoryItemAdmin, AssetIssueAdmin
)
# System
from app.admin.system import AnnouncementAdmin, SystemSnapshotAdmin


def setup_admin(app) -> Admin:
    """
    Admin panel بناتا ہے اور سب views register کرتا ہے۔
    Authentication:
      is_superuser → full CRUD
      is_staff     → read-only
    """
    auth = AdminAuth(secret_key="dms-admin-key-2026")
    admin = Admin(
        app,
        engine,
        base_url="/admin",
        authentication_backend=auth,
        title="DMS Admin Panel"
    )

    # ── Core ──────────────────────────────────
    admin.add_view(InstitutionAdmin)
    admin.add_view(CourseAdmin)
    admin.add_view(FacilityAdmin)
    admin.add_view(TimetableAdmin)
    admin.add_view(ClassSessionAdmin)

    # ── People ────────────────────────────────
    admin.add_view(UserAdmin)
    admin.add_view(StaffAdmin)
    admin.add_view(ParentAdmin)
    admin.add_view(StudentAdmin)
    admin.add_view(AdmissionAdmin)
    admin.add_view(StaffAttendanceAdmin)
    admin.add_view(AttendanceAdmin)
    admin.add_view(ActivityLogAdmin)

    # ── Finance ───────────────────────────────
    admin.add_view(FeeAdmin)
    admin.add_view(FeePaymentAdmin)
    admin.add_view(WalletTransactionAdmin)
    admin.add_view(DonorAdmin)
    admin.add_view(IncomeAdmin)
    admin.add_view(ExpenseAdmin)
    admin.add_view(StaffAdvanceAdmin)

    # ── Inventory ─────────────────────────────
    admin.add_view(ItemCategoryAdmin)
    admin.add_view(InventoryItemAdmin)
    admin.add_view(AssetIssueAdmin)

    # ── System ────────────────────────────────
    admin.add_view(AnnouncementAdmin)
    admin.add_view(SystemSnapshotAdmin)

    return admin

