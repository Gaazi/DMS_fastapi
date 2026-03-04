from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime, time as dt_time
from decimal import Decimal

# Models
from app.models import Institution, Course, Admission, ClassSession, Student
from app.logic.audit import AuditManager

class CourseManager:
    """Business logic for courses, admissions, and class sessions (FastAPI/SQLModel Version)"""
    
    def __init__(self, session: Session, user: Any, target: Any = None, institution: Optional[Institution] = None):
        """یوزر، سیشن، ادارے یا کسی مخصوص تعلیمی پروگرام (Course) کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        
        if isinstance(target, Institution):
             self.institution = target
             self.course = None
        elif isinstance(target, Course):
             self.course = target
             self.institution = self.session.get(Institution, target.inst_id)
        else:
             self.course = None
             self.institution = institution
             
        # Resolve institution from user profile if not provided
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = self.session.get(Institution, user.staff.inst_id)
            elif user:
                statement = select(Institution).where(Institution.user_id == user.id)
                self.institution = session.exec(statement).first()

    def _parse_date(self, d_str: Any, default: Any = None) -> Optional[dt_date]:
        if not d_str: return default
        if isinstance(d_str, dt_date): return d_str
        if isinstance(d_str, datetime): return d_str.date()
        s = str(d_str).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
            try: return datetime.strptime(s, fmt).date()
            except: continue
        return default

    def _parse_time(self, t_str: Any) -> Optional[dt_time]:
        if not t_str: return None
        if isinstance(t_str, dt_time): return t_str
        for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p'):
            try: return datetime.strptime(t_str, fmt).time()
            except: continue
        return None

    def _check_access(self):
        """سیکیورٹی چیک: پروگرام اور داخلوں کی مینجمنٹ کے حقوق کی تصدیق۔"""
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if getattr(self.user, 'is_superuser', False): return True
        if not self.institution: raise HTTPException(status_code=404, detail="Institution context missing.")

        is_owner = (self.user.id == self.institution.user_id)
        is_staff = hasattr(self.user, 'staff') and self.user.staff and (self.user.staff.inst_id == self.institution.id)
        
        if not (is_owner or is_staff):
            raise HTTPException(status_code=403, detail="Access denied.")
        return True

    def save_course(self, data: dict):
        """نئے تعلیمی پروگرام (Course) کا اندراج کرنا یا پرانے کو اپڈیٹ کرنا۔"""
        self._check_access()
        course_id = data.get('id')
        if course_id:
            course = self.session.get(Course, course_id)
            if not course: raise HTTPException(status_code=404, detail="Course not found")
            for k, v in data.items(): 
                if hasattr(course, k): setattr(course, k, v)
            action = "update"
        else:
            course = Course(**data)
            course.inst_id = self.institution.id
            self.session.add(course)
            action = "create"
            
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, action, 'Course', course.id or 0, course.title, data)
        self.session.commit()
        self.session.refresh(course)
        return True, "Course information has been saved successfully.", course

    def delete_course(self, course_id: int):
        """کسی پروگرام اور اس سے جڑے تمام ریکارڈز (داخلے، سیشنز) کو حذف کرنا۔"""
        self._check_access()
        course = self.session.get(Course, course_id)
        if not course or course.inst_id != self.institution.id:
            raise HTTPException(status_code=404, detail="Course not found.")
            
        name = course.title
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'delete', 'Course', course_id, name, {})
        self.session.delete(course)
        self.session.commit()
        return True, f"Course '{name}' has been deleted.", None

    def enroll_student(self, student_id: int, data: dict):
        """کسی طالب علم کو مخصوص پروگرام میں داخل (Admission) کرنے کی لاجک۔"""
        self._check_access()
        if not self.course: raise HTTPException(status_code=400, detail="Course context required.")
        
        # Check if already enrolled
        existing = self.session.exec(select(Admission).where(
            Admission.student_id == student_id, 
            Admission.course_id == self.course.id,
            Admission.status == 'active'
        )).first()
        if existing:
            return False, "This student is already actively enrolled in this course.", existing
            
        # Capacity check
        if self.course.capacity and self.course.student_count >= self.course.capacity:
            return False, f"Course capacity ({self.course.capacity}) has been reached.", None

        # Extract valid fields
        admission = Admission(
            student_id=student_id,
            course_id=self.course.id,
            admission_date=self._parse_date(data.get('enrollment_date'), dt_date.today()),
            roll_no=data.get('roll_no'),
            admission_fee_discount=Decimal(str(data.get('admission_fee_discount', 0))),
            agreed_admission_fee=Decimal(str(data.get('agreed_admission_fee'))) if data.get('agreed_admission_fee') else None,
            course_fee_discount=Decimal(str(data.get('course_fee_discount', 0))),
            agreed_course_fee=Decimal(str(data.get('agreed_course_fee'))) if data.get('agreed_course_fee') else None,
            fee_start_month=self._parse_date(data.get('fee_start_month')),
            fee_type_override=data.get('fee_type_override'),
            status='active'
        )
        self.session.add(admission)
        self.session.flush()

        # Generate Fees & Payments
        from app.logic.finance import FinanceManager
        fm = FinanceManager(self.session, self.institution, self.user)
        fm.generate_initial_fees_for_admission(admission)

        # Initial Payment
        initial_pay = data.get('initial_payment', 0)
        if initial_pay and float(initial_pay) > 0:
            from app.logic.payments import Cashier
            cashier = Cashier(self.session, self.institution, self.user)
            cashier.collect_fee(student_id=student_id, amount=Decimal(str(initial_pay)), method=data.get('payment_method', 'Cash'))
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'enroll', 'Admission', admission.id or 0, f"Student {student_id}", data)
        self.session.commit()
        self.session.refresh(admission)
        return True, "Student admission has been completed.", admission

    def update_admission(self, admission_id: int, status: str):
        """داخلے کی حیثیت (Status) تبدیل کرنا۔"""
        self._check_access()
        admission = self.session.get(Admission, admission_id)
        if not admission or (self.course and admission.course_id != self.course.id):
             raise HTTPException(status_code=404, detail="Admission record not found.")
        
        old_status = admission.status
        admission.status = status
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'update_admission', 'Admission', admission_id, f"Status: {old_status} -> {status}", {"status": status})
        self.session.commit()
        return True, f"Admission status updated to {status}.", admission

    def delete_admission(self, admission_id: int):
        """داخلہ حذف کرنا۔"""
        self._check_access()
        admission = self.session.get(Admission, admission_id)
        if not admission: raise HTTPException(status_code=404, detail="Admission not found.")
        
        self.session.delete(admission)
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'delete_admission', 'Admission', admission_id, "Record deleted", {})
        self.session.commit()
        return True, "Admission record deleted.", None

    def save_session(self, data: dict):
        """تعلیمی پروگرام کے تحت ایک انفرادی کلاس سیشن کا شیڈول بنانا یا اپڈیٹ کرنا۔"""
        self._check_access()
        if not self.course: raise HTTPException(status_code=400, detail="Course context required.")
        
        session_id = data.get('session_id') or data.get('id')
        if session_id:
            class_session = self.session.get(ClassSession, int(session_id))
            if not class_session: raise HTTPException(status_code=404, detail="Session not found")
            
            if 'date' in data: class_session.date = self._parse_date(data.get('date'), class_session.date)
            if 'start_time' in data: class_session.start_time = self._parse_time(data.get('start_time'))
            if 'end_time' in data: class_session.end_time = self._parse_time(data.get('end_time'))
            if 'topic' in data: class_session.topic = data.get('topic')
            if 'session_type' in data: class_session.session_type = data.get('session_type')
            if 'notes' in data: class_session.notes = data.get('notes')
            action = "update_session"
        else:
            class_session = ClassSession(
                course_id=self.course.id,
                date=self._parse_date(data.get('date'), dt_date.today()),
                start_time=self._parse_time(data.get('start_time')),
                end_time=self._parse_time(data.get('end_time')),
                topic=data.get('topic', 'Daily'),
                session_type=data.get('session_type', 'class'),
                notes=data.get('notes', '')
            )
            self.session.add(class_session)
            action = "schedule_session"
            
        self.session.flush()
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, action, 'ClassSession', class_session.id or 0, class_session.topic or 'Daily', data)
        self.session.commit()
        self.session.refresh(class_session)
        return True, "Class session saved successfully.", class_session

    def delete_session(self, session_id: int):
        """سیشن حذف کرنا۔"""
        self._check_access()
        class_session = self.session.get(ClassSession, session_id)
        if not class_session: raise HTTPException(status_code=404, detail="Session not found.")
        
        self.session.delete(class_session)
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'delete_session', 'ClassSession', session_id, "Session deleted", {})
        self.session.commit()
        return True, "Session deleted successfully.", None


    def get_stats(self):
        """موجودہ پروگرام کے کل طلبہ اور سیشنز کا مجموعی خلاصہ (Stats)۔"""
        if not self.course: return {}
        
        total_students = self.session.exec(select(func.count(Admission.id)).where(Admission.course_id == self.course.id)).one()
        active_students = self.session.exec(select(func.count(Admission.id)).where(Admission.course_id == self.course.id, Admission.status == 'active')).one()
        total_sessions = self.session.exec(select(func.count(ClassSession.id)).where(ClassSession.course_id == self.course.id)).one()
        
        return {
            'total_students': total_students,
            'active_students': active_students,
            'total_sessions': total_sessions
        }

    def get_detail_context(self):
        """کورس کے پروفائل صفحے کے لیے تمام داخلے، سیشنز اور اسٹیٹس کا ڈیٹا تیار کرنا۔"""
        if not self.course: raise HTTPException(status_code=404, detail="Course not set.")
        
        admissions = self.session.exec(select(Admission).where(Admission.course_id == self.course.id).order_by(desc(Admission.admission_date))).all()
        sessions = self.session.exec(select(ClassSession).where(ClassSession.course_id == self.course.id).order_by(desc(ClassSession.date), desc(ClassSession.id))).all()
        
        # Available staff to assign
        from app.models import Staff
        all_staff = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id).order_by(Staff.name)).all()

        return {
            "institution": self.institution,
            "course": self.course,
            "admissions": admissions,
            "sessions": sessions,
            "stats": self.get_stats(),
            "all_staff": all_staff
        }

    def assign_instructor(self, staff_id: int):
        """کسی استاد/خادم کو پروگرام کی ذمہ داری سونپنا۔"""
        self._check_access()
        if not self.course: raise HTTPException(status_code=400, detail="Course context required.")
        staff = self.session.get(Staff, staff_id)
        if not (staff and staff.inst_id == self.institution.id):
            raise HTTPException(status_code=404, detail="Staff member not found.")
        
        if staff not in self.course.instructors:
            self.course.instructors.append(staff)
            self.session.flush()
            AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'assign_instructor', 'Course', self.course.id, f"Assigned {staff.name}", {"staff_id": staff_id})
            self.session.commit()
            return True, f"Instructor {staff.name} assigned.", staff
        return False, "Already assigned.", staff

    def remove_instructor(self, staff_id: int):
        """پروگرام سے کسی استاد کو ہٹانا۔"""
        self._check_access()
        if not self.course: raise HTTPException(status_code=400, detail="Course context required.")
        staff = self.session.get(Staff, staff_id)
        if not staff: raise HTTPException(status_code=404, detail="Staff not found.")
        
        if staff in self.course.instructors:
            self.course.instructors.remove(staff)
            self.session.flush()
            AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'remove_instructor', 'Course', self.course.id, f"Removed {staff.name}", {"staff_id": staff_id})
            self.session.commit()
            return True, "Instructor removed.", None
        return False, "Instructor not part of this course.", None


