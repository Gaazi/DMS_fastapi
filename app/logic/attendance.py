from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime, timedelta
import calendar

# Models
# Models
from ..models import Institution, Student, Staff, Attendance, Staff_Attendance, ClassSession, Admission
from .audit import AuditManager

class AttendanceManager:
    """
    ادارے کی تمام حاضریوں (اسٹاف اور طلبہ) کا مرکزی مرکز۔ (FastAPI/SQLModel Version)
    """
    
    def __init__(self, session: Session, institution: Optional[Institution] = None, user: Any = None):
        """یوزر، سیشن اور ادارے کی معلومات کے ساتھ حاضری مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        self.institution = institution
        
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = self.session.get(Institution, user.staff.inst_id)
            elif user:
                statement = select(Institution).where(Institution.user_id == user.id)
                self.institution = session.exec(statement).first()
        
    def _check_permission(self):
        """چیک کرنا کہ کیا موجودہ یوزر کو حاضری کے ریکارڈز دیکھنے یا تبدیل کرنے کی اجازت ہے۔"""
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if getattr(self.user, 'is_superuser', False): return True
        if not self.institution: raise HTTPException(status_code=404, detail="Institution context not found.")
        
        is_owner = (self.user.id == self.institution.user_id)
        is_staff = hasattr(self.user, 'staff') and self.user.staff and (self.user.staff.inst_id == self.institution.id)
        
        if not (is_owner or is_staff):
            raise HTTPException(status_code=403, detail="Access denied.")
        return True

    def get_prepared_list(self, type='student', target_date=None, course_id=None):
        """فارم کے لیے طلبہ یا اسٹاف کی فہرست تیار کرنا۔"""
        self._check_permission()
        target_date = target_date or dt_date.today()
        
        if type == 'staff':
            members = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True).order_by(Staff.name)).all()
            records_stmt = select(Staff_Attendance).where(Staff_Attendance.inst_id == self.institution.id, Staff_Attendance.date == target_date)
            field_id = 'staff_member_id'
        else:
            stmt = select(Student).where(Student.inst_id == self.institution.id, Student.is_active == True)
            if course_id:
                stmt = stmt.join(Admission).where(Admission.course_id == course_id, Admission.status == 'active')
            
            members = self.session.exec(stmt.order_by(Student.name)).all()
            
            # طالب علم کی حاضری سیشن پر مبنی ہوتی ہے
            records_stmt = select(Attendance).where(Attendance.inst_id == self.institution.id)
            if course_id:
                records_stmt = records_stmt.join(ClassSession).where(ClassSession.course_id == course_id, ClassSession.date == target_date)
            else:
                records_stmt = records_stmt.join(ClassSession).where(ClassSession.date == target_date)
            
            field_id = 'student_id'

        records = self.session.exec(records_stmt).all()
        attendance_map = {getattr(r, field_id): r for r in records}
        
        for m in members:
            rec = attendance_map.get(m.id)
            m.current_status = rec.status if rec else 'present'
            m.current_remarks = rec.remarks if rec else ''
            # Helper flags for UI
            m.is_absent = (m.current_status == 'absent')
            m.is_late = (m.current_status == 'late' or getattr(rec, 'is_late', False))
            m.is_excused = (m.current_status == 'excused')
            
        return members, target_date, course_id

    def save_bulk(self, type: str, post_data: dict, target_date: dt_date, course_id: Optional[int] = None):
        """کئی طلبہ یا ملازمین کی حاضری ایک ساتھ ڈیٹا بیس میں محفوظ کرنا۔"""
        self._check_permission()
        target_date = target_date or dt_date.today()
        
        if type == 'staff':
            members = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True)).all()
            for m in members:
                status = post_data.get(f"staff_{m.id}") or 'present'
                remarks = post_data.get(f"remarks_{m.id}", "")
                
                stmt = select(Staff_Attendance).where(Staff_Attendance.staff_member_id == m.id, Staff_Attendance.date == target_date)
                record = self.session.exec(stmt).first()
                if not record:
                    record = Staff_Attendance(staff_member_id=m.id, inst_id=self.institution.id, date=target_date)
                
                record.status = status
                record.remarks = remarks
                self.session.add(record)
        else:
            if not course_id: return False, "کورس کا انتخاب ضروری ہے۔"
            
            session_stmt = select(ClassSession).where(ClassSession.course_id == course_id, ClassSession.date == target_date)
            class_session = self.session.exec(session_stmt).first()
            if not class_session:
                class_session = ClassSession(course_id=course_id, date=target_date)
                self.session.add(class_session)
                self.session.flush()

            members = self.session.exec(select(Student).join(Admission).where(
                Admission.course_id == course_id, 
                Admission.status == 'active'
            )).all()
            
            for m in members:
                status = post_data.get(f"student_{m.id}") or 'present'
                remarks = post_data.get(f"remarks_{m.id}", "")
                
                stmt = select(Attendance).where(Attendance.student_id == m.id, Attendance.session_id == class_session.id)
                record = self.session.exec(stmt).first()
                if not record:
                    record = Attendance(student_id=m.id, session_id=class_session.id, inst_id=self.institution.id)
                
                record.status = status
                record.remarks = remarks
                self.session.add(record)

        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'bulk_attendance', type.capitalize(), 0, f"Attendance for {type} on {target_date}", {'course_id': course_id})
        self.session.commit()
        return True, "حاضری کامیابی سے محفوظ کر لی گئی ہے۔"



    def get_todays_live_summary(self):
        """آج کی حاضری کا خلاصہ (کتنے فیصد حاضر ہیں) ڈیش بورڈ پر دکھانے کے لیے۔"""
        if not self.institution: return {'total': 0, 'present_count': 0, 'absent': 0, 'percentage': 0}
        
        today = dt_date.today()
        total_students = self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id, Student.is_active == True)).one()
        
        # آج کے سیشنز میں حاضر طلبہ
        stmt = select(func.count(func.distinct(Attendance.student_id))).join(ClassSession).where(
            Attendance.inst_id == self.institution.id,
            ClassSession.date == today,
            Attendance.status == 'present'
        )
        present_count = self.session.exec(stmt).one() or 0
        
        return {
            'total': total_students,
            'present_count': present_count,
            'absent': max(0, total_students - present_count),
            'percentage': round((present_count / total_students * 100), 1) if total_students > 0 else 0
        }

    def get_attendance_report(self, start_date: dt_date, end_date: dt_date):
        """مخصوص دورانیے کے لیے اسٹاف اور طلبہ کی حاضری کا مکمل تجزیہ اور رپورٹ۔"""
        self._check_permission()
        
        # اسٹاف اسٹیٹس
        staff_stmt = select(func.count(Staff_Attendance.id), Staff_Attendance.status).where(
            Staff_Attendance.inst_id == self.institution.id,
            Staff_Attendance.date >= start_date,
            Staff_Attendance.date <= end_date
        ).group_by(Staff_Attendance.status)
        staff_res = self.session.exec(staff_stmt).all()
        
        # یہاں مزید تفصیلی رپورٹ لاجک کو SQLModel میں تبدیل کیا جا سکتا ہے (جینگو کی طرح مکمل سٹیٹس)
        # فی الحال بنیادی ڈیٹا مہیا کیا جا رہا ہے
        return {
            'staff_summary': staff_res,
            'day_span': (end_date - start_date).days + 1,
            'no_records': False
        }
