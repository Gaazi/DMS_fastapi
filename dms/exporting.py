from __future__ import annotations

import io
import json
import zipfile
import tablib
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable, List, Sequence, Tuple

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Functions:
   - collect_institution_export_dataset (Line 67) - Aggregates all model data
   - export_institution_to_json/excel/csv (Line 128-136)
   - export_institutions_bundle (Line 144) - Creates ZIP with media/JSON
   - import_institution_from_json (Line 178) - Handles data restoration
"""

from django.core import serializers
from django.db.models import Model

from .models import (
    Attendance,
    ClassSession,
    Donor,
    Enrollment,
    Expense,
    Facility,
    Income,
    Institution,
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
    ExamResult,
)
from .resources import (
    InstitutionResource, CourseResource, FacilityResource,
    StudentResource, StaffResource, ParentResource, EnrollmentResource,
    ClassSessionResource, AttendanceResource, StaffAttendanceResource,
    AnnouncementResource, FeeResource, FeePaymentResource,
    DonorResource, IncomeResource, ExpenseResource, WalletTransactionResource,
    ExamResource, ExamResultResource
)

def _get_resource_mapping() -> List[Tuple[str, type, any]]:
    return [
        ("Institution", InstitutionResource, lambda inst: [inst]),
        ("Courses", CourseResource, lambda inst: Course.objects.filter(institution=inst)),
        ("Facilities", FacilityResource, lambda inst: Facility.objects.filter(institution=inst)),
        ("Students", StudentResource, lambda inst: Student.objects.filter(institution=inst)),
        ("Staff", StaffResource, lambda inst: Staff.objects.filter(institution=inst)),
        ("Parents", ParentResource, lambda inst: Parent.objects.filter(institution=inst)),
        ("Enrollments", EnrollmentResource, lambda inst: Enrollment.objects.filter(course__institution=inst)),
        ("Class Sessions", ClassSessionResource, lambda inst: ClassSession.objects.filter(course__institution=inst)),
        ("Attendance", AttendanceResource, lambda inst: Attendance.objects.filter(session__course__institution=inst)),
        ("Staff Attendance", StaffAttendanceResource, lambda inst: Staff_Attendance.objects.filter(institution=inst)),
        ("Announcements", AnnouncementResource, lambda inst: Announcement.objects.filter(institution=inst)),
        ("Fees", FeeResource, lambda inst: Fee.objects.filter(institution=inst)),
        ("Fee Payments", FeePaymentResource, lambda inst: Fee_Payment.objects.filter(institution=inst)),
        ("Donors", DonorResource, lambda inst: Donor.objects.filter(institution=inst)),
        ("Income", IncomeResource, lambda inst: Income.objects.filter(institution=inst)),
        ("Expenses", ExpenseResource, lambda inst: Expense.objects.filter(institution=inst)),
        ("Wallet Transactions", WalletTransactionResource, lambda inst: WalletTransaction.objects.filter(student__institution=inst)),
        ("Exams", ExamResource, lambda inst: Exam.objects.filter(institution=inst)),
        ("Exam Results", ExamResultResource, lambda inst: ExamResult.objects.filter(exam__institution=inst)),
    ]

def collect_institution_export_dataset(institution: Institution) -> tablib.Databook:
    book = tablib.Databook()
    
    # 1. پہلے تمام انفرادی شیٹس شامل کریں
    for label, resource_class, queryset_func in _get_resource_mapping():
        resource = resource_class()
        queryset = queryset_func(institution)
        dataset = resource.export(queryset)
        dataset.title = label
        book.add_sheet(dataset)

    # 2. اب ایک 'Master Ledger' (مکمل اکاؤنٹ لیجر) شیٹ بنائیں جو سب کو یکجا کرے
    ledger_data = []
    
    # آمدنی (Income)
    for inc in Income.objects.filter(institution=institution).order_by('date'):
        ledger_data.append([
            inc.date.isoformat(), 
            "آمدنی (Income)", 
            inc.get_source_display() or inc.source, 
            inc.description or "", 
            float(inc.amount), 
            float(inc.amount), 
            0.0
        ])
    
    # اخراجات (Expenses)
    for exp in Expense.objects.filter(institution=institution).order_by('date'):
        ledger_data.append([
            exp.date.isoformat(), 
            "خرچ (Expense)", 
            exp.get_category_display() or exp.category, 
            exp.description or "", 
            float(exp.amount), 
            0.0, 
            float(exp.amount)
        ])
        
    # فیس کی وصولی (Fee Payments)
    for pay in Fee_Payment.objects.filter(institution=institution).order_by('payment_date'):
        ledger_data.append([
            pay.payment_date.date().isoformat(), 
            "فیس وصولی (Fees)", 
            f"طالب علم: {pay.student.name if pay.student else 'Unknown'}", 
            f"رسید: {pay.receipt_number}", 
            float(pay.amount), 
            float(pay.amount), 
            0.0
        ])

    # تاریخ کے لحاظ سے ترتیب دیں
    ledger_data.sort(key=lambda x: x[0], reverse=True)
    
    ledger_headers = ["تاریخ", "قسم", "مد / کیٹیگری", "تفصیل", "کل رقم", "آمدنی (جمع)", "خرچ (بنام)"]
    ledger_sheet = tablib.Dataset(*ledger_data, headers=ledger_headers)
    ledger_sheet.title = "مکمل لیجر (Accounts)"
    
    book.add_sheet(ledger_sheet)
    
    return book

def export_institution_to_json(institution: Institution, *, indent: int | None = 2) -> str:
    book = collect_institution_export_dataset(institution)
    return book.export("json")

def export_institution_to_excel(institution: Institution) -> bytes:
    book = collect_institution_export_dataset(institution)
    return book.export("xlsx")

def export_institution_to_csv_zip(institution: Institution) -> bytes:
    book = collect_institution_export_dataset(institution)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for sheet in book.sheets():
            archive.writestr(f"{sheet.title}.csv", sheet.export("csv"))
    return buffer.getvalue()

def export_institutions_bundle(
    institutions: Iterable[Institution],
    *,
    include_json: bool = True,
    include_excel: bool = True,
    include_csv: bool = True,
    include_media: bool = True,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for institution in institutions:
            slug = institution.slug or f"institution-{institution.pk}"
            safe_slug = slug.replace("/", "_")
            book = collect_institution_export_dataset(institution)
            
            if include_json:
                archive.writestr(f"{safe_slug}/{safe_slug}.json", book.export("json"))
            
            if include_excel:
                archive.writestr(f"{safe_slug}/{safe_slug}.xlsx", book.export("xlsx"))
                
            if include_csv:
                for sheet in book.sheets():
                    archive.writestr(f"{safe_slug}/csv/{sheet.title}.csv", sheet.export("csv"))
            
            if include_media:
                # کٹھے میڈیا فائلز شامل کریں
                # 1. ادارے کا لوگو
                if institution.logo and hasattr(institution.logo, 'path'):
                    try:
                        archive.write(institution.logo.path, f"{safe_slug}/media/{institution.logo.name}")
                    except (FileNotFoundError, ValueError):
                        pass

                # 2. طلبہ کی تصاویر
                for student in Student.objects.filter(institution=institution):
                    if student.photo and hasattr(student.photo, 'path'):
                        try:
                            archive.write(student.photo.path, f"{safe_slug}/media/{student.photo.name}")
                        except (FileNotFoundError, ValueError):
                            pass

                # 3. اسٹاف کی تصاویر
                for staff in Staff.objects.filter(institution=institution):
                    if staff.photo and hasattr(staff.photo, 'path'):
                        try:
                            archive.write(staff.photo.path, f"{safe_slug}/media/{staff.photo.name}")
                        except (FileNotFoundError, ValueError):
                            pass
                    
    return buffer.getvalue()

def export_all_institutions_bundle(*, include_json: bool = True, include_excel: bool = True, include_csv: bool = True, include_media: bool = True) -> bytes:
    return export_institutions_bundle(
        Institution.objects.all().order_by("name"),
        include_json=include_json,
        include_excel=include_excel,
        include_csv=include_csv,
        include_media=include_media,
    )

def import_institution_from_json(institution: Institution, json_data: str) -> dict:
    """
    پورے ادارے کا ڈیٹا ایک ہی JSON (Databook format) سے ری اسٹور کرتا ہے۔
    یہ لائبریری (django-import-export) کے انجن کو استعمال کرتا ہے۔
    """
    book = tablib.Databook()
    book.json = json_data
    
    results = {}
    
    # 1. ریسورسز کی ترتیب (Order of import focus)
    ordered_sheet_names = [
        "Institution", "Courses", "Facilities", "Students", "Staff", 
        "Parents", "Enrollments", "Class Sessions", "Exams"
    ]
    other_sheets = [sheet.title for sheet in book.sheets() if sheet.title not in ordered_sheet_names and sheet.title != "مکمل لیجر (Accounts)"]
    
    final_order = ordered_sheet_names + other_sheets
    mapping = {label: res for label, res, _ in _get_resource_mapping()}
    
    from django.db import transaction
    
    try:
        with transaction.atomic():
            for label in final_order:
                sheet = next((s for s in book.sheets() if s.title == label), None)
                if not sheet or not sheet.dict:
                    continue
                
                resource_class = mapping.get(label)
                if not resource_class:
                    continue
                    
                resource = resource_class()
                result = resource.import_data(sheet, dry_run=False, raise_errors=True)
                results[label] = {
                    "total": len(sheet),
                    "created": result.totals.get('new', 0),
                    "updated": result.totals.get('update', 0),
                    "skipped": result.totals.get('skip', 0),
                }
    except Exception as e:
        return {"error": str(e)}
        
    return results