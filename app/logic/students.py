from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime
from decimal import Decimal
import json
import re

# Models
from app.models import Institution, Student, Course, Attendance, ClassSession, Fee, Admission, User
from app.models.attendance import DailyAttendance
from app.logic.audit import AuditManager

class StudentManager:    
    """
    مرکزی کوآرڈینیٹر (Student Pillar Hub) - (FastAPI/SQLModel ورژن)
    """
    def __init__(self, session: Session, user: Any, institution: Optional[Institution] = None, student: Optional[Student] = None):
        self.user = user
        self.session = session
        self.institution = institution
        self.student = student

        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = session.get(Institution, user.staff.inst_id)
            else:
                self.institution = session.exec(select(Institution).where(Institution.user_id == user.id)).first()

        if self.student and not self.institution:
            self.institution = session.get(Institution, self.student.inst_id)

    def _check_access(self, target_student: Optional[Student] = None):
        """رسائی کے حقوق چیک کرنا۔"""
        if not self.user: raise HTTPException(status_code=401, detail="Authentication required.")
        if getattr(self.user, 'is_superuser', False): return True
        curr_student = target_student or self.student
        
        if self.institution:
            is_staff = hasattr(self.user, 'staff') and self.user.staff and (self.user.staff.inst_id == self.institution.id)
            is_owner = (self.user.id == self.institution.user_id)
            if is_staff or is_owner: return True
                
        if curr_student:
            # Check if user is the student themselves
            # This logic depends on your Auth User -> Student link
            pass
                    
        raise HTTPException(status_code=403, detail="Access Denied.")

    def set_student(self, student: Student):
        self.student = student
        if student and not self.institution:
            self.institution = self.session.get(Institution, student.inst_id)
        return self

    def finance(self): 
        from app.logic.finance import FinanceManager
        return FinanceManager(self.session, self.institution, self.user, student=self.student)

    def attendance(self): 
        from app.logic.attendance import AttendanceManager
        return AttendanceManager(self.session, self.institution, self.user)

    def get_student_list(self, q: Optional[str] = None, course_id: Optional[int] = None, status: str = 'active', page: int = 1):
        """طلبہ کی مکمل فہرست مع حاضری اور فیس کے اعداد و شمار۔"""
        self._check_access()
        page_size = 20
        
        # بنیادی کوئری
        statement = select(Student).where(Student.inst_id == self.institution.id)
        
        # 1. فلٹرنگ
        if q:
            statement = statement.where(or_(
                Student.name.contains(q), Student.mobile.contains(q), Student.reg_id.contains(q)
            ))
            
        if status == 'active': statement = statement.where(Student.is_active == True)
        elif status == 'inactive': statement = statement.where(Student.is_active == False)

        if course_id:
            statement = statement.join(Admission).where(Admission.course_id == course_id)

        statement = statement.distinct()

        # 2. اعداد و شمار
        results = self.session.exec(statement.order_by(Student.name).offset((page-1)*page_size).limit(page_size)).all()
        
        students_data = []
        today = dt_date.today()
        start_of_month = today.replace(day=1)

        for s in results:
            # حاضری (اس مہینے کی - کلاس اور ڈے حاضری ملا کر)
            class_presents = self.session.exec(select(func.count(Attendance.id)).join(ClassSession).where(
                Attendance.student_id == s.id,
                Attendance.status == 'present',
                ClassSession.date >= start_of_month
            )).one() or 0
            
            day_presents = self.session.exec(select(func.count(DailyAttendance.id)).where(
                DailyAttendance.student_id == s.id,
                DailyAttendance.status == 'present',
                DailyAttendance.date >= start_of_month
            )).one() or 0
            
            presents = class_presents + day_presents
            
            # بقایاجات (Due Fees)
            due_amount = self.session.exec(select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
                Fee.student_id == s.id, Fee.status.in_(['Pending', 'Partial'])
            )).one() or 0

            # Attach extra data to the object for template compatibility
            s.month_presents = presents
            s.month_absents = 0 # Placeholder or calculate
            s.month_due_amount = float(due_amount)
            s.has_pending_fee = (due_amount > 0)
            students_data.append(s)

        base_count_stmt = select(func.count(Student.id)).where(Student.inst_id == self.institution.id)
        if status == 'active':
            base_count_stmt = base_count_stmt.where(Student.is_active == True)
        elif status == 'inactive':
            base_count_stmt = base_count_stmt.where(Student.is_active == False)
            
        return {
            "students": students_data,
            "total": self.session.exec(base_count_stmt).one(),
            "stats": self._get_global_stats()
        }

    def _get_global_stats(self):
        """پورے ادارے کے طلبہ کے مجموعی اعداد و شمار۔"""
        return {
            "total": self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id)).one(),
            "active": self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id, Student.is_active == True)).one(),
            "inactive": self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id, Student.is_active == False)).one(),
        }

    def save_student(self, data: dict, enrollment_data: Optional[dict] = None):
        """طالب علم کو محفوظ کرنا اور رجسٹریشن لاجک کو سنبھالنا۔"""
        self._check_access()
        
        # 1. Hybrid Datalist Logic
        full_name = data.get('name', '').strip()
        match = re.match(r"^(.*)\s*\[(\w+)\]$", full_name)
        student = None

        if match:
            reg_id = match.group(2).strip()
            student = self.session.exec(select(Student).where(Student.inst_id == self.institution.id, Student.reg_id == reg_id)).first()

        if not student:
            if 'id' in data and data['id']:
                student = self.session.get(Student, data['id'])
                if student:
                    for k, v in data.items(): 
                        if hasattr(student, k): setattr(student, k, v)
                    action = "update"
            
            if not student:
                # Robust reg_id generation (Format: InstPrefix-InstID-S-Serial)
                if not data.get('reg_id'):
                    inst_prefix = (self.institution.reg_id or self.institution.slug[:3] or "INST").upper()
                    inst_id_padded = f"{self.institution.id:03d}"
                    inst_count = self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id)).one()
                    serial = inst_count + 1
                    data['reg_id'] = f"{inst_prefix}-{inst_id_padded}-S-{serial}"
                    
                    # Double check for reg_id uniqueness in this institution & increment serial if collision
                    while self.session.exec(select(Student).where(Student.inst_id == self.institution.id, Student.reg_id == data['reg_id'])).first():
                        serial += 1
                        data['reg_id'] = f"{inst_prefix}-{inst_id_padded}-S-{serial}"

                if not data.get('admission_date'):
                    data['admission_date'] = dt_date.today()

                student = Student(**data)
                student.inst_id = self.institution.id
                self.session.add(student)
                action = "create"
        else:
            for k, v in data.items(): 
                if hasattr(student, k): setattr(student, k, v)
            action = "update"

        # 1.5 Handle Parent/Family Linking
        guardian_name = (data.get('guardian_name') or data.get('father_name', '')).strip()
        guardian_mobile = data.get('mobile', '').strip() or data.get('mobile2', '').strip()
        
        if guardian_name and guardian_mobile:
            from app.models import Parent
            # Try to find existing parent by mobile in this institution
            parent = self.session.exec(select(Parent).where(Parent.inst_id == self.institution.id, Parent.mobile == guardian_mobile)).first()
            
            if not parent:
                # Generate Family ID
                inst_prefix = (self.institution.reg_id or self.institution.slug[:3] or "INST").upper()
                parent_count = self.session.exec(select(func.count(Parent.id)).where(Parent.inst_id == self.institution.id)).one()
                serial = parent_count + 1
                family_id = f"{inst_prefix}-F-{serial:04d}"
                
                # Uniqueness check for family_id
                while self.session.exec(select(Parent).where(Parent.inst_id == self.institution.id, Parent.family_id == family_id)).first():
                    serial += 1
                    family_id = f"{inst_prefix}-F-{serial:04d}"

                parent = Parent(
                    name=guardian_name,
                    mobile=guardian_mobile,
                    inst_id=self.institution.id,
                    family_id=family_id,
                    relationship=data.get('guardian_relation', 'father')
                )
                self.session.add(parent)
                self.session.flush()
            
            # Link student to parent if not already linked
            if student not in parent.students:
                parent.students.append(student)
                self.session.add(parent)

        self.session.commit()
        self.session.refresh(student)

        # 2. Admission (Enrollment) via CourseManager
        if enrollment_data and enrollment_data.get('course_id'):
            from app.logic.courses import CourseManager
            course_obj = self.session.get(Course, enrollment_data['course_id'])
            if course_obj:
                cm = CourseManager(self.session, self.user, target=course_obj)
                # Map Student Schema to Course Enrollment Format
                enroll_params = {
                    'enrollment_date': dt_date.today(),
                    'agreed_admission_fee': enrollment_data.get('admission_fee'),
                    'agreed_course_fee': enrollment_data.get('agreed_fee'),
                    'initial_payment': enrollment_data.get('initial_payment', 0),
                    'payment_method': enrollment_data.get('payment_method', 'Cash'),
                    'roll_no': enrollment_data.get('roll_no')
                }
                cm.enroll_student(student.id, enroll_params)

        AuditManager.log_activity(self.session, self.institution.id, self.user.id, action, 'Student', student.id, student.name, data)
        self.session.commit()
        self.session.refresh(student)
        return student


    def update_status(self, student_id: int, is_active: bool):
        """طالب علم اور اس کے داخلوں (Admissions) کا اسٹیٹس بدلنا۔"""
        self._check_access()
        student = self.session.get(Student, student_id)
        if not student: raise HTTPException(status_code=404, detail="Student not found.")
        
        student.is_active = is_active
        self.session.add(student)
        
        # داخلوں کو سنک کریں
        status_to_set = 'active' if is_active else 'paused'
        admissions = self.session.exec(select(Admission).where(Admission.student_id == student_id, Admission.status.in_(['active', 'paused', 'pending']))).all()
        for ad in admissions:
            ad.status = status_to_set
            self.session.add(ad)
            
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'update_status', 'Student', student.id, student.name, {'active': is_active})
        self.session.commit()
        return True

    def promote_student(self, student_id: int, new_course_id: int):
        """طالب علم کو ایک کلاس سے نکال کر دوسری میں پروموٹ کرنا۔"""
        student = self.session.get(Student, student_id)
        self.set_student(student)._check_access()
        
        # 1. پرانے ریکارڈ مکمل کریں
        old_ads = self.session.exec(select(Admission).where(Admission.student_id == student_id, Admission.status == 'active')).all()
        for ad in old_ads:
            ad.status = 'completed'
            self.session.add(ad)
            
        # 2. نیا داخلہ
        new_ad = Admission(student_id=student_id, course_id=new_course_id, status='active', admission_date=dt_date.today())
        self.session.add(new_ad)
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'promote', 'Student', student_id, student.name, {'to_course': new_course_id})
        self.session.commit()
        return True


    def get_student_detail_context(self, student_id: int):
        """مکمل پروفائل ڈیٹا بشمول والٹ اور حاضری۔"""
        student = self.session.get(Student, student_id)
        if not student: raise HTTPException(status_code=404, detail="Student not found.")
        self.set_student(student)._check_access()
        from app.models.finance import WalletTransaction, Fee
        
        fees = self.finance().student_fee_history()
        fee_totals = self.finance().get_student_fee_totals()
        att_summary = self.attendance().get_member_summary(student)
        
        # Find the first fee that isn't fully paid
        first_pending_fee = next((f for f in fees if f.status != 'Paid'), None)
        
        wallet_history = self.session.exec(
            select(WalletTransaction).where(WalletTransaction.student_id == student.id).order_by(desc(WalletTransaction.date)).limit(20)
        ).all()
        
        admissions = self.session.exec(
            select(Admission).where(Admission.student_id == student.id)
        ).all()
        
        # Attach course-specific attendance to each admission
        for ad in admissions:
            # Bypass Pydantic's strict __setattr__ by setting _attendance directly
            object.__setattr__(ad, "_attendance", self.attendance().get_member_summary(student, course_id=ad.course_id))

        from app.logic.institution import InstitutionManager
        return {
            "student": student,
            "fees": fees,
            "fee_totals": fee_totals,
            "fee_balance": fee_totals['balance'],
            "first_pending_fee": first_pending_fee,
            "wallet_history": wallet_history,
            "wallet_balance": getattr(student, 'wallet_balance', 0),
            "admissions": admissions,
            "enrollments": admissions, # Alias for template partials
            "attendance": self.attendance().session.exec(
                select(Attendance).where(Attendance.student_id == student.id).join(ClassSession).order_by(desc(ClassSession.date)).limit(10)
            ).all(),
            "daily_attendance": self.attendance().session.exec(
                select(DailyAttendance).where(DailyAttendance.student_id == student.id).order_by(desc(DailyAttendance.date)).limit(10)
            ).all(),
            "attendance_percentage": att_summary['percentage'],
            "total_daily_records": att_summary['total'],
            "currency_label": InstitutionManager.get_currency_label(self.institution),
        }

