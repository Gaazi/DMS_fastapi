from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime, timedelta
import calendar

# Models
from app.models import Institution, Student, Staff, Attendance, Staff_Attendance, ClassSession, Admission, TimetableItem, DailyAttendance
from app.logic.audit import AuditManager

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

    def get_prepared_list(self, type='student', target_date=None, course_id=None, session_id=None):
        """فارم کے لیے طلبہ یا اسٹاف کی فہرست تیار کرنا۔"""
        self._check_permission()
        target_date = target_date or dt_date.today()
        
        # If session_id is provided, prioritize it
        if type == 'student' and session_id:
            class_session = self.session.get(ClassSession, session_id)
            if class_session:
                course_id = class_session.course_id
                target_date = class_session.date
        
        if type == 'staff':
            members = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True).order_by(Staff.name)).all()
            records_stmt = select(Staff_Attendance).where(Staff_Attendance.inst_id == self.institution.id, Staff_Attendance.date == target_date)
            field_id = 'staff_member_id'
        else:
            stmt = select(Student).where(Student.inst_id == self.institution.id, Student.is_active == True)
            if course_id:
                stmt = stmt.join(Admission).where(Admission.course_id == course_id, Admission.status == 'active')
            
            stmt = stmt.distinct()
            members = self.session.exec(stmt.order_by(Student.name)).all()
            
            # طالب علم کی حاضری سیشن یا ڈے پر مبنی ہوتی ہے
            if session_id:
                records_stmt = select(Attendance).where(Attendance.inst_id == self.institution.id, Attendance.session_id == session_id)
            elif course_id:
                records_stmt = select(Attendance).join(ClassSession).where(
                    Attendance.inst_id == self.institution.id, 
                    ClassSession.course_id == course_id, 
                    ClassSession.date == target_date
                )
            else:
                records_stmt = select(DailyAttendance).where(DailyAttendance.inst_id == self.institution.id, DailyAttendance.date == target_date)
            
            field_id = 'student_id'
            
            # If we are looking at session/course, also fetch DailyAttendance as fallback for UI
            daily_fallback_map = {}
            if session_id or course_id:
                daily_records = self.session.exec(
                    select(DailyAttendance).where(
                        DailyAttendance.inst_id == self.institution.id, 
                        DailyAttendance.date == target_date
                    )
                ).all()
                daily_fallback_map = {r.student_id: r for r in daily_records}
            
        records = self.session.exec(records_stmt).all()
        attendance_map = {getattr(r, field_id): r for r in records}
        
        for m in members:
            rec = attendance_map.get(m.id)
            if not rec and type != 'staff':
                # Use daily fallback if specifically for students and no class record exists
                rec = daily_fallback_map.get(m.id)
                
            m.current_status = rec.status if rec else 'present'
            m.current_remarks = rec.remarks if rec else ''
            
            # Helper flags for UI
            m.is_absent = (m.current_status == 'absent')
            m.is_late = (m.current_status == 'late' or getattr(rec, 'is_late', False))
            m.is_excused = (m.current_status == 'excused')
            
        return members, target_date, course_id, session_id

    def get_sessions(self, course_id: Optional[int], target_date: dt_date):
        """کورس اور تاریخ کی بنیاد پر سیشنز کی لسٹ حاصل کرنا (بشمول شیڈول)۔"""
        self._check_permission()
        
        # Auto-create sessions from TimetableItem if missing
        day_of_week = str(target_date.weekday())
        tt_stmt = select(TimetableItem).where(TimetableItem.day_of_week == day_of_week, TimetableItem.is_active == True)
        if course_id:
            tt_stmt = tt_stmt.where(TimetableItem.course_id == course_id)
            
        timetable_items = self.session.exec(tt_stmt).all()
        new_sessions = False
        
        for tt in timetable_items:
            exists_stmt = select(ClassSession).where(
                ClassSession.course_id == tt.course_id,
                ClassSession.date == target_date,
                ClassSession.start_time == tt.start_time,
                ClassSession.topic == tt.subject
            )
            if not self.session.exec(exists_stmt).first():
                new_session = ClassSession(
                    course_id=tt.course_id,
                    date=target_date,
                    start_time=tt.start_time,
                    end_time=tt.end_time,
                    topic=tt.subject,
                    session_type="class"
                )
                self.session.add(new_session)
                new_sessions = True
                
        if new_sessions:
            self.session.commit()

        stmt = select(ClassSession).where(ClassSession.date == target_date)
        if course_id:
            stmt = stmt.where(ClassSession.course_id == course_id)
        
        stmt = stmt.order_by(ClassSession.start_time)
        return self.session.exec(stmt).all()


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
            session_id = post_data.get('session_id')
            class_session = None
            
            if session_id:
                class_session = self.session.get(ClassSession, int(session_id))
                if class_session and not course_id:
                    course_id = class_session.course_id
                    
            if not course_id and not class_session:
                # ====== ڈے حاضری (Day Attendance) ======
                members = self.session.exec(select(Student).where(
                    Student.inst_id == self.institution.id, 
                    Student.is_active == True
                )).all()

                for m in members:
                    status = post_data.get(f"student_{m.id}") or 'present'
                    remarks = post_data.get(f"remarks_{m.id}", "")
                    
                    stmt = select(DailyAttendance).where(
                        DailyAttendance.student_id == m.id, 
                        DailyAttendance.date == target_date
                    )
                    record = self.session.exec(stmt).first()
                    
                    if not record:
                        record = DailyAttendance(student_id=m.id, inst_id=self.institution.id, date=target_date)
                    
                    record.status = status
                    record.remarks = remarks
                    self.session.add(record)
                    
            else:
                # ====== سیشن یا کورس کی حاضری ======
                if not class_session:
                    if not course_id:
                        return False, "کورس کا انتخاب ضروری ہے۔"
                    session_stmt = select(ClassSession).where(ClassSession.course_id == course_id, ClassSession.date == target_date)
                    class_session = self.session.exec(session_stmt).first()
                    if not class_session:
                        class_session = ClassSession(course_id=course_id, date=target_date)
                        self.session.add(class_session)
                        self.session.flush()

                members = self.session.exec(select(Student).join(Admission).where(
                    Admission.course_id == class_session.course_id, 
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
        
        # آج کے سیشنز جن میں طالب علم کی حاضری لگی ہے (اکلاس اور ڈے حاضری ملا کر)
        # To calculate properly with fallback, we fetch all today's sessions,
        # all today's Attendance and all today's DailyAttendance
        sessions = self.session.exec(select(ClassSession).where(ClassSession.date == today)).all()
        session_ids = [s.id for s in sessions]
        
        explicit_att = self.session.exec(select(Attendance).where(
            Attendance.inst_id == self.institution.id, Attendance.session_id.in_(session_ids) if session_ids else False
        )).all()
        
        daily_att = self.session.exec(select(DailyAttendance).where(
            DailyAttendance.inst_id == self.institution.id, DailyAttendance.date == today
        )).all()
        
        # Build maps
        explicit_map = {(a.student_id, a.session_id): a.status for a in explicit_att}
        daily_map = {a.student_id: a.status for a in daily_att}
        
        present_str, absent_str, late_str = 'present', 'absent', 'late'
        p_c, a_c, l_c = 0, 0, 0
        
        # We need to map which student is in which session based on admissions
        admissions = self.session.exec(select(Admission).where(Admission.status == 'active')).all()
        course_students = {}
        for adm in admissions:
            course_students.setdefault(adm.course_id, []).append(adm.student_id)
            
        student_counted = set()
        
        for s in sessions:
            stds = course_students.get(s.course_id, [])
            for sid in stds:
                if (sid, s.id) in student_counted: continue
                # We count distinct students for today's live summary
                status = explicit_map.get((sid, s.id)) or daily_map.get(sid)
                if status == present_str: p_c += 1
                elif status == absent_str: a_c += 1
                elif status == late_str: l_c += 1
                if status: student_counted.add((sid, s.id))
                
        # Count unique students present/absent/late today (overall)
        # Actually Dashboard usually shows unique students count, so we use max priority status per student today?
        # Let's adjust simple unique counts like before
        student_status_today = {}
        for s in sessions:
            stds = course_students.get(s.course_id, [])
            for sid in stds:
                status = explicit_map.get((sid, s.id)) or daily_map.get(sid)
                if status and sid not in student_status_today:
                    student_status_today[sid] = status
                    
        present_count = sum(1 for st in student_status_today.values() if st == present_str)
        absent_count = sum(1 for st in student_status_today.values() if st == absent_str)
        late_count = sum(1 for st in student_status_today.values() if st == late_str)
        
        return {
            'total': total_students,
            'present_count': present_count,
            'absent': absent_count,
            'late': late_count,
            'not_marked': max(0, total_students - (present_count + absent_count + late_count)),
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
    def get_member_summary(self, member, days=30, course_id: Optional[int] = None) -> dict:
        """کسی ایک طالب علم یا ملازم کی حاضری کا مختصر خلاصہ۔"""
        end_date = dt_date.today()
        start_date = end_date - timedelta(days=days-1)
        
        if isinstance(member, Student):
            # Find all sessions for courses the student is enrolled in
            admissions = self.session.exec(select(Admission).where(Admission.student_id == member.id, Admission.status == 'active')).all()
            course_ids = [a.course_id for a in admissions]
            
            if course_id:
                if course_id in course_ids: course_ids = [course_id]
                else: course_ids = []
                
            sessions = self.session.exec(select(ClassSession).where(
                ClassSession.course_id.in_(course_ids) if course_ids else False,
                ClassSession.date >= start_date, ClassSession.date <= end_date
            )).all()
            
            session_ids = [s.id for s in sessions]
            
            # Get explicit class attendance
            explicit_att = self.session.exec(select(Attendance).where(
                Attendance.student_id == member.id,
                Attendance.session_id.in_(session_ids) if session_ids else False
            )).all()
            explicit_map = {a.session_id: a.status for a in explicit_att}
            
            # Get daily fallbacks
            daily_att = self.session.exec(select(DailyAttendance).where(
                DailyAttendance.student_id == member.id,
                DailyAttendance.date >= start_date, DailyAttendance.date <= end_date
            )).all()
            daily_map = {a.date: a.status for a in daily_att}
            
            summary = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': 0}
            for s in sessions:
                status = explicit_map.get(s.id) or daily_map.get(s.date)
                if status:
                    summary['total'] += 1
                    if status in summary: summary[status] += 1
                    
        else:
            stmt = select(Staff_Attendance).where(
                Staff_Attendance.staff_member_id == member.id,
                Staff_Attendance.date >= start_date
            )
            records = self.session.exec(stmt).all()
            
            summary = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': len(records)}
            for r in records:
                if r.status in summary:
                    summary[r.status] += 1
        
        summary['percentage'] = round((summary['present'] / summary['total'] * 100), 1) if summary['total'] > 0 else 0
        return summary

# Final end of file
