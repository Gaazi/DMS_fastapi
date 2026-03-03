from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime

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
        
        # Extract valid fields
        admission = Admission(
            student_id=student_id,
            course_id=self.course.id,
            admission_date=dt_date.today(),
            roll_no=data.get('roll_no'),
            admission_fee_discount=Decimal(str(data.get('admission_fee_discount', 0))),
            agreed_admission_fee=Decimal(str(data.get('agreed_admission_fee'))) if data.get('agreed_admission_fee') else None,
            course_fee_discount=Decimal(str(data.get('course_fee_discount', 0))),
            agreed_course_fee=Decimal(str(data.get('agreed_course_fee'))) if data.get('agreed_course_fee') else None,
            fee_start_month=datetime.strptime(data['fee_start_month'], '%Y-%m').date() if data.get('fee_start_month') else None,
            fee_type_override=data.get('fee_type_override'),
            status='active'
        )
        self.session.add(admission)
        self.session.flush()
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'enroll', 'Admission', admission.id or 0, f"Student {student_id}", data)
        self.session.commit()
        self.session.refresh(admission)
        return True, "Student admission has been completed.", admission

    def save_session(self, data: dict):
        """تعلیمی پروگرام کے تحت ایک انفرادی کلاس سیشن کا شیڈول بنانا۔"""
        self._check_access()
        if not self.course: raise HTTPException(status_code=400, detail="Course context required.")
        
        class_session = ClassSession(
            course_id=self.course.id,
            inst_id=self.institution.id,
            date=data.get('date', dt_date.today()),
            start_time=data.get('start_time'),
            end_time=data.get('end_time'),
            room_id=data.get('room_id'),
            topic=data.get('topic', 'Daily'),
            description=data.get('description', '')
        )
        
        self.session.add(class_session)
        self.session.flush()
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'schedule_session', 'ClassSession', class_session.id or 0, data.get('topic', 'Daily'), data)
        self.session.commit()
        self.session.refresh(class_session)
        return True, "Class session scheduled successfully.", class_session


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
        
        return {
            "institution": self.institution,
            "course": self.course,
            "admissions": admissions,
            "sessions": sessions,
            "stats": self.get_stats()
        }


