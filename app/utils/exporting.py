from __future__ import annotations

import io
import json
import zipfile
import tablib
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable, List, Sequence, Tuple, Optional
from sqlmodel import Session, select

# Internal Imports
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
    ExamResult,
)
from app.helper.resources import (
    InstitutionResource, CourseResource, FacilityResource,
    StudentResource, StaffResource, ParentResource, EnrollmentResource,
    ClassSessionResource, AttendanceResource, StaffAttendanceResource,
    AnnouncementResource, FeeResource, FeePaymentResource,
    DonorResource, IncomeResource, ExpenseResource, WalletTransactionResource,
    ExamResource, ExamResultResource
)

def _get_resource_mapping() -> List[Tuple[str, type, any]]:
    """Returns a list of tuples containing (label, resource_class, query_lambda)."""
    return [
        ("Institution", InstitutionResource, lambda inst, s: [inst]),
        ("Courses", CourseResource, lambda inst, s: s.exec(select(Course).where(Course.inst_id == inst.id)).all()),
        ("Facilities", FacilityResource, lambda inst, s: s.exec(select(Facility).where(Facility.inst_id == inst.id)).all()),
        ("Students", StudentResource, lambda inst, s: s.exec(select(Student).where(Student.inst_id == inst.id)).all()),
        ("Staff", StaffResource, lambda inst, s: s.exec(select(Staff).where(Staff.inst_id == inst.id)).all()),
        ("Parents", ParentResource, lambda inst, s: s.exec(select(Parent).where(Parent.inst_id == inst.id)).all()),
        ("Enrollments", EnrollmentResource, lambda inst, s: s.exec(select(Enrollment).join(Course).where(Course.inst_id == inst.id)).all()),
        ("Class Sessions", ClassSessionResource, lambda inst, s: s.exec(select(ClassSession).join(Course).where(Course.inst_id == inst.id)).all()),
        ("Attendance", AttendanceResource, lambda inst, s: s.exec(select(Attendance).join(ClassSession).join(Course).where(Course.inst_id == inst.id)).all()),
        ("Staff Attendance", StaffAttendanceResource, lambda inst, s: s.exec(select(Staff_Attendance).where(Staff_Attendance.inst_id == inst.id)).all()),
        ("Announcements", AnnouncementResource, lambda inst, s: s.exec(select(Announcement).where(Announcement.inst_id == inst.id)).all()),
        ("Fees", FeeResource, lambda inst, s: s.exec(select(Fee).where(Fee.inst_id == inst.id)).all()),
        ("Fee Payments", FeePaymentResource, lambda inst, s: s.exec(select(Fee_Payment).where(Fee_Payment.inst_id == inst.id)).all()),
        ("Donors", DonorResource, lambda inst, s: s.exec(select(Donor).where(Donor.inst_id == inst.id)).all()),
        ("Income", IncomeResource, lambda inst, s: s.exec(select(Income).where(Income.inst_id == inst.id)).all()),
        ("Expenses", ExpenseResource, lambda inst, s: s.exec(select(Expense).where(Expense.inst_id == inst.id)).all()),
        ("Wallet Transactions", WalletTransactionResource, lambda inst, s: s.exec(select(WalletTransaction).join(Student).where(Student.inst_id == inst.id)).all()),
        ("Exams", ExamResource, lambda inst, s: s.exec(select(Exam).where(Exam.inst_id == inst.id)).all()),
        ("Exam Results", ExamResultResource, lambda inst, s: s.exec(select(ExamResult).join(Exam).where(Exam.inst_id == inst.id)).all()),
    ]

def collect_institution_export_dataset(institution: Institution, session: Session) -> tablib.Databook:
    book = tablib.Databook()
    
    # 1. پہلے تمام انفرادی شیٹس شامل کریں
    for label, resource_class, queryset_func in _get_resource_mapping():
        resource = resource_class()
        queryset = queryset_func(institution, session)
        dataset = resource.export(queryset)
        dataset.title = label
        book.add_sheet(dataset)

    # 2. اب ایک 'Master Ledger' شیٹ بنائیں
    ledger_data = []
    
    # آمدنی (Income)
    incomes = session.exec(select(Income).where(Income.inst_id == institution.id).order_by(Income.date)).all()
    for inc in incomes:
        ledger_data.append([
            inc.date.isoformat() if hasattr(inc.date, 'isoformat') else str(inc.date), 
            "آؐمدنی (Income)", 
            inc.source, 
            inc.description or "", 
            float(inc.amount), 
            float(inc.amount), 
            0.0
        ])
    
    # اخراجات (Expenses)
    expenses = session.exec(select(Expense).where(Expense.inst_id == institution.id).order_by(Expense.date)).all()
    for exp in expenses:
        ledger_data.append([
            exp.date.isoformat() if hasattr(exp.date, 'isoformat') else str(exp.date), 
            "خرچ (Expense)", 
            exp.category, 
            exp.description or "", 
            float(exp.amount), 
            0.0, 
            float(exp.amount)
        ])
        
    # فیس کی وصولی (Fee Payments)
    payments = session.exec(select(Fee_Payment).where(Fee_Payment.institution_id == institution.id).order_by(Fee_Payment.payment_date)).all()
    for pay in payments:
        ledger_data.append([
            pay.payment_date.isoformat() if hasattr(pay.payment_date, 'isoformat') else str(pay.payment_date), 
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

def export_institution_to_json(institution: Institution, session: Session, *, indent: int | None = 2) -> str:
    book = collect_institution_export_dataset(institution, session)
    return book.export("json")

def export_institution_to_excel(institution: Institution, session: Session) -> bytes:
    book = collect_institution_export_dataset(institution, session)
    return book.export("xlsx")

def export_institution_to_csv_zip(institution: Institution, session: Session) -> bytes:
    book = collect_institution_export_dataset(institution, session)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for sheet in book.sheets():
            archive.writestr(f"{sheet.title}.csv", sheet.export("csv"))
    return buffer.getvalue()

def export_institutions_bundle(institutions: Iterable[Institution], session: Session) -> bytes:
    """ایک سے زیادہ اداروں کا مکمل ڈیٹا ایک بنڈل (ZIP) میں محفوظ کرنا۔"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for inst in institutions:
            json_payload = export_institution_to_json(inst, session)
            archive.writestr(f"{inst.slug}/data.json", json_payload)
    return buffer.getvalue()

def export_all_institutions_bundle(session: Session) -> bytes:
    """پورے سسٹم کا بیک اپ۔"""
    institutions = session.exec(select(Institution)).all()
    return export_institutions_bundle(institutions, session)

def import_institution_from_json(institution: Institution, session: Session, json_content: str) -> dict:
    """JSON ڈیٹا سے کسی بھی ادارے کا ریکارڈ بحال کرنا۔"""
    book = tablib.Databook()
    book.json = json_content
    
    results = {}
    for label, resource_class, _ in _get_resource_mapping():
        resource = resource_class()
        # Find matching sheet
        sheet = next((s for s in book.sheets() if s.title == label), None)
        if sheet:
            res = resource.import_data(sheet, session)
            results[label] = res.totals
            
    return results
