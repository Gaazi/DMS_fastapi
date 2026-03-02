from django.urls import path, re_path
from django.views.generic import RedirectView
from . import views

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Sections:
   - Auth & Core (Line 10)
   - Institution Types (Line 32)
   - Staff Management (Line 42)
   - Student & Attendance (Line 50)
   - Data Export/Import (Line 56)
   - Backup Snapshots (Line 62)
   - Finance (Incomes/Expenses/Fees) (Line 82)
   - Guardians & Private views (Line 98)
"""


# Common pattern to avoid repetition
type_pattern = "<slug:institution_slug>"

urlpatterns = [
    # 1. Authentication & General Paths
    path("login/", views.dms_login, name="dms_login"),
    path("logout/", views.dms_logout, name="dms_logout"),
    path("signup/", views.signup, name="dms_signup"),
    path("account/set-default/<slug:institution_slug>/", views.set_default_institution, name="set_default_institution"),
    path(f"{type_pattern}/notifications/", views.all_notifications, name="all_notifications"),
    path("manifest.json", views.manifest, name="manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("share-target/", views.share_target, name="share_target"),
    path("shortcut/<str:action>/", views.smart_shortcut, name="smart_shortcut"),
    path("", views.dms, name="dms"),
    path("welcome/", views.no_institution_linked, name="no_institution_linked"),
    path("overview/", views.institution_overview, name="institution_overview"),
    path("backup/all/", views.download_all_institutions_export, name="all_institutions_export"),
    path("backup/restore/", views.restore_system_backup, name="system_restore"),
    
    # Legacy Redirects (پرانے لنکس کے لیے)
    # path("types/<str:institution_type>/", views.institution_type_list),

    # Global System Backups (Superuser only)
    path("backup/system/", views.create_manual_snapshot, name="system_create_manual_snapshot"),
    path("backup/system/history/", views.backup_manager, name="system_backup_manager"),
    path("backup/system/restore/<int:snapshot_id>/", views.restore_snapshot_ajax, name="system_restore_snapshot_ajax"),
    path("backup/system/delete/<int:snapshot_id>/", views.delete_snapshot, name="system_delete_snapshot"),
    path("backup/system/download/<int:snapshot_id>/", views.download_snapshot_file, name="system_download_snapshot_file"),

    # 2. اسمارٹ کیٹیگری لنکس (بغیر types/ کے)
    # re_path(r'^(?P<institution_type>masjid|madrasa|maktab)/$', views.institution_type_list, name="institution_type_list"),
    # path("masjid/", views.institution_type_list, {'institution_type': 'masjid'}, name="masjid_list"),
    # path("madrasa/", views.institution_type_list, {'institution_type': 'madrasa'}, name="madrasa_list"),
    # path("maktab/", views.institution_type_list, {'institution_type': 'maktab'}, name="maktab_list"),
    
    # 3. Main Dashboard Paths (Using type_pattern)
    path(f"{type_pattern}/", views.dashboard, name="dashboard"),
    path(f"{type_pattern}/login/", views.dms_login, name="institution_login"),
    path(f"{type_pattern}/logout/", views.dms_logout, name="institution_logout"),
    path(f"{type_pattern}/details/", views.institution_detail, name="institution_detail"),
    path(f"{type_pattern}/admin-tools/", views.admin_tools_view, name="institution_admin_tools"),
    path(f"{type_pattern}/accounts-manager/", views.manage_accounts, name="manage_accounts"),
    path(f"{type_pattern}/account/create/<str:person_type>/<int:person_id>/", views.create_portal_account, name="create_portal_account"),
    
    # Staff
    path(f"{type_pattern}/staff/", views.staff, name="dms_staff"),
    path(f"{type_pattern}/staff/detail/<int:staff_id>/", views.staff_detail, name="dms_staff_detail"),
    path(f"{type_pattern}/staff/manage/add/", views.staff_create_edit, name="dms_staff_create"),
    path(f"{type_pattern}/staff/manage/edit/<int:staff_id>/", views.staff_create_edit, name="dms_staff_edit"),
    path(f"{type_pattern}/staff/attendance/", views.staff_attendance, name="staff_attendance"),
    path(f"{type_pattern}/staff/payroll/", views.process_monthly_payroll, name="staff_payroll"),
    
    # Students
    path(f"{type_pattern}/students/", views.student, name="students"),
    path(f"{type_pattern}/students/dashboard/<int:student_id>/", views.student_dashboard, name="student_dashboard"),
    path(f"{type_pattern}/students/admission/", views.admission, name="admission"),
    path(f"{type_pattern}/students/list/", views.student_list_details, name="student_list"),
    path(f"{type_pattern}/students/detail/<int:student_id>/", views.student_detail, name="student_detail"),
    path(f"{type_pattern}/students/promote/<int:student_id>/", views.promote_to_staff, name="promote_to_staff"),
    path(f"{type_pattern}/students/attendance/", views.student_attendance, name="student_attendance"),
    path(f"{type_pattern}/attendance/report/", views.attendance_report, name="attendance_report"),
    
    # Exports
    path(f"{type_pattern}/export/", views.download_institution_export, name="institution_export"),

    # Mosque Aliases (Visual URLs)
    path(f"{type_pattern}/members/", views.student, name="musalleen_list"),
    path(f"{type_pattern}/members/detail/<int:student_id>/", views.student_detail, name="musalleen_detail"),
    path(f"{type_pattern}/members/add/", views.admission, name="musallee_admission"),
    path(f"{type_pattern}/programs/", views.course, name="program_list"),
    path(f"{type_pattern}/programs/<int:course_id>/", views.course_detail, name="program_detail"),
    path(f"{type_pattern}/export/full/", views.download_institution_export_bundle, name="institution_export_bundle"),
    path(f"{type_pattern}/export/sheets/", views.download_institution_export_sheet, name="institution_export_sheet"),
    path(f"{type_pattern}/import/restore/", views.restore_institution_backup, name="institution_import_restore"),
    
    # Snapshots (Backup System)
    path(f"{type_pattern}/backup/", views.create_manual_snapshot, name="create_manual_snapshot"),
    path(f"{type_pattern}/backup/history/", views.backup_manager, name="backup_manager"),
    path(f"{type_pattern}/backup/history/restore/<int:snapshot_id>/", views.restore_snapshot_ajax, name="restore_snapshot_ajax"),
    path(f"{type_pattern}/backup/history/delete/<int:snapshot_id>/", views.delete_snapshot, name="delete_snapshot"),
    path(f"{type_pattern}/backup/history/download/<int:snapshot_id>/", views.download_snapshot_file, name="download_snapshot_file"),
    
    # Courses
    path(f"{type_pattern}/course/", views.course, name="dms_course"),
    path(f"{type_pattern}/course/<int:course_id>/", views.course_detail, name="dms_course_detail"),
    
    path(f"{type_pattern}/sessions/<int:session_id>/attendance/", views.session_attendance, name="dms_session_attendance"),
    
    # Facilities
    path(f"{type_pattern}/facilities/", views.facility_list, name="dms_facilities"),
    
    # Finances
    path(f"{type_pattern}/in/", views.donation, name="income"),
    path(f"{type_pattern}/in/list/", views.donation_in_overview, name="income_list") ,
    path(f"{type_pattern}/in/create/", views.donation_in_create, name="income_create"),
    path(f"{type_pattern}/in/<int:income_id>/", views.income_detail, name="income_detail"),
    path(f"{type_pattern}/in/<int:income_id>/edit/", views.income_edit, name="income_edit"),
    path(f"{type_pattern}/join/", views.public_admission, name="public_admission"),
    path(f"{type_pattern}/support/", views.public_donation, name="public_support"),
    path(f"{type_pattern}/donor/", views.donor, name="donor"),
    path(f"{type_pattern}/donor/add/", views.donor_create, name="donor_create"),
    path(f"{type_pattern}/donor/quick-save/", views.donor_create_quick, name="donor_create_quick"),
    path(f"{type_pattern}/donor/<int:donor_id>/", views.donor_detail, name="donor_detail"),
    path(f"{type_pattern}/donor/<int:donor_id>/edit/", views.donor_edit, name="donor_edit"),
    path(f"{type_pattern}/donor/<int:donor_id>/delete/", views.donor_delete, name="donor_delete"),
    
    path(f"{type_pattern}/out/", views.expense, name="expense"),
    path(f"{type_pattern}/out/<int:expense_id>/", views.expense_detail, name="expense_detail"),
    path(f"{type_pattern}/out/<int:expense_id>/edit/", views.expense_edit, name="expense_edit"),
    path(f"{type_pattern}/out/transaction-report/", views.transaction_report, name="transaction_report"),
    path(f"{type_pattern}/out/create/", views.expense_out_create, name="expense_out_create"),
    
    path(f"{type_pattern}/balance/", views.balance, name="balance"),

    # 4. Fees Management
    path(f"{type_pattern}/fees/<int:fee_id>/", views.fees, name="fees"),
    path(f"{type_pattern}/fees/<int:fee_id>/pay/", views.pay_installment, name="pay_installment"),
    path(f"{type_pattern}/fees/generate-batch/", views.batch_generate_fees, name="batch_generate_fees"),
    
    # Guardian / Scoped Views
    path(f"{type_pattern}/guardian/", views.guardian_dashboard, name="guardian_dashboard_scoped"),
    path(f"{type_pattern}/guardian/students/<int:student_id>/", views.student_dashboard, name="student_dashboard_scoped"),
    
    # 5. Inventory & Library
    path(f"{type_pattern}/inventory/", views.inventory_dashboard, name="inventory_dashboard"),
    path(f"{type_pattern}/inventory/add/", views.add_item_view, name="add_item"),
    path(f"{type_pattern}/inventory/issue/", views.issue_item_view, name="issue_item"),
    path(f"{type_pattern}/inventory/return/<int:issue_id>/", views.return_item_view, name="return_item"),

    # 6. Timetable & Scheduling
    path(f"{type_pattern}/timetable/", views.timetable_view, name="timetable"),

    # 7. System Audit & Recycle Bin
    path(f"{type_pattern}/logs/", views.audit_logs, name="audit_logs"),
    path(f"{type_pattern}/trash/", views.recycle_bin, name="recycle_bin"),

    # 8. Data APIs
]
