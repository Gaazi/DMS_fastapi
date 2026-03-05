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
        """فارم کے لیے طلبہ یا اسٹاف کی فہرست تیار کرنا - تمام حاضری موڈ (ڈے، کورس، سیشن) کو سپورٹ کرتا ہے۔"""
        self._check_permission()
        target_date = target_date or dt_date.today()
        
        # session_id سے course_id اور date نکالنا
        if type == 'student' and session_id:
            class_session = self.session.get(ClassSession, session_id)
            if class_session:
                course_id = class_session.course_id
                target_date = class_session.date
        
        if type == 'staff':
            # ====== اسٹاف حاضری لسٹ ======
            members = self.session.exec(
                select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True).order_by(Staff.name)
            ).all()
            records = self.session.exec(
                select(Staff_Attendance).where(
                    Staff_Attendance.inst_id == self.institution.id,
                    Staff_Attendance.date == target_date
                )
            ).all()
            att_map = {r.staff_member_id: r for r in records}
            
            for m in members:
                rec = att_map.get(m.id)
                m.current_status = rec.status if rec else 'present'
                m.current_remarks = rec.remarks if rec else ''
                m.is_absent = (m.current_status == 'absent')
                m.is_late = (m.current_status == 'late')
                m.is_excused = (m.current_status == 'excused')
                
        else:
            # ====== طالب علم حاضری لسٹ ======
            stmt = select(Student).where(Student.inst_id == self.institution.id, Student.is_active == True)
            if course_id:
                stmt = stmt.join(Admission).where(Admission.course_id == course_id, Admission.status == 'active')
            members = self.session.exec(stmt.distinct().order_by(Student.name)).all()
            
            # ڈے حاضری (fallback)
            daily_records = self.session.exec(
                select(DailyAttendance).where(
                    DailyAttendance.inst_id == self.institution.id,
                    DailyAttendance.date == target_date
                )
            ).all()
            daily_map = {r.student_id: r for r in daily_records}
            
            # مخصوص کلاس/سیشن حاضری
            class_map = {}
            if session_id:
                # مخصوص گھنٹے کی حاضری پڑھنا
                records = self.session.exec(
                    select(Attendance).where(
                        Attendance.inst_id == self.institution.id,
                        Attendance.session_id == session_id
                    )
                ).all()
                class_map = {r.student_id: r for r in records}
            
            for m in members:
                if session_id:
                    # مخصوص گھنٹہ: class_map → daily_map → present
                    rec = class_map.get(m.id) or daily_map.get(m.id)
                elif course_id:
                    # صرف کورس: صرف daily_map پڑھنا (کیونکہ save بھی DailyAttendance میں ہوتا ہے)
                    rec = daily_map.get(m.id)
                else:
                    # ڈے حاضری: سب کی daily_map
                    rec = daily_map.get(m.id)
                m.current_status = rec.status if rec else 'present'
                m.current_remarks = rec.remarks if rec else ''
                m.is_absent = (m.current_status == 'absent')
                m.is_late = (m.current_status == 'late')
                m.is_excused = (m.current_status == 'excused')
            
        return members, target_date, course_id, session_id

    def get_sessions(self, course_id: Optional[int], target_date: dt_date):
        """کورس اور تاریخ کی بنیاد پر سیشنز کی لسٹ حاصل کرنا (بشمول شیڈول)۔"""
        self._check_permission()
        
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
            members = self.session.exec(
                select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True)
            ).all()
            for m in members:
                status = post_data.get(f"staff_{m.id}") or 'present'
                remarks = post_data.get(f"remarks_{m.id}", "")
                rec = self.session.exec(
                    select(Staff_Attendance).where(
                        Staff_Attendance.staff_member_id == m.id,
                        Staff_Attendance.date == target_date
                    )
                ).first()
                if not rec:
                    rec = Staff_Attendance(staff_member_id=m.id, inst_id=self.institution.id, date=target_date)
                rec.status = status
                rec.remarks = remarks
                self.session.add(rec)

        else:
            # فارم سے session_id پڑھنا
            form_session_id = post_data.get('session_id')
            class_session = None
            
            if form_session_id:
                class_session = self.session.get(ClassSession, int(form_session_id))
                if class_session and not course_id:
                    course_id = class_session.course_id
                    
            if class_session:
                # ====== مخصوص گھنٹہ کی حاضری (ClassAttendance) ======
                members = self.session.exec(
                    select(Student).join(Admission).where(
                        Admission.course_id == class_session.course_id,
                        Admission.status == 'active',
                        Student.inst_id == self.institution.id,
                        Student.is_active == True
                    )
                ).all()
                
                for m in members:
                    status = post_data.get(f"student_{m.id}") or 'present'
                    remarks = post_data.get(f"remarks_{m.id}", "")
                    rec = self.session.exec(
                        select(Attendance).where(
                            Attendance.student_id == m.id,
                            Attendance.session_id == class_session.id
                        )
                    ).first()
                    if not rec:
                        rec = Attendance(student_id=m.id, session_id=class_session.id, inst_id=self.institution.id)
                    rec.status = status
                    rec.remarks = remarks
                    self.session.add(rec)

            elif course_id:
                # ====== صرف کورس منتخب ہو (کوئی سیشن نہیں): DailyAttendance میں سیو ======
                # اس سے ملٹی سیشن والی پیچیدکی ختم ہوتی ہے
                members = self.session.exec(
                    select(Student).join(Admission).where(
                        Admission.course_id == course_id,
                        Admission.status == 'active',
                        Student.inst_id == self.institution.id,
                        Student.is_active == True
                    )
                ).all()
                
                for m in members:
                    status = post_data.get(f"student_{m.id}") or 'present'
                    remarks = post_data.get(f"remarks_{m.id}", "")
                    rec = self.session.exec(
                        select(DailyAttendance).where(
                            DailyAttendance.student_id == m.id,
                            DailyAttendance.date == target_date
                        )
                    ).first()
                    if not rec:
                        rec = DailyAttendance(student_id=m.id, inst_id=self.institution.id, date=target_date)
                    rec.status = status
                    rec.remarks = remarks
                    self.session.add(rec)

            else:
                # ====== ڈے حاضری - تمام طلبہ کے لیے ======
                members = self.session.exec(
                    select(Student).where(
                        Student.inst_id == self.institution.id,
                        Student.is_active == True
                    )
                ).all()

                for m in members:
                    status = post_data.get(f"student_{m.id}") or 'present'
                    remarks = post_data.get(f"remarks_{m.id}", "")
                    rec = self.session.exec(
                        select(DailyAttendance).where(
                            DailyAttendance.student_id == m.id,
                            DailyAttendance.date == target_date
                        )
                    ).first()
                    if not rec:
                        rec = DailyAttendance(student_id=m.id, inst_id=self.institution.id, date=target_date)
                    rec.status = status
                    rec.remarks = remarks
                    self.session.add(rec)
        
        AuditManager.log_activity(
            self.session, self.institution.id, self.user.id,
            'bulk_attendance', type.capitalize(), 0,
            f"Attendance for {type} on {target_date}",
            {'course_id': course_id}
        )
        self.session.commit()
        return True, "حاضری کامیابی سے محفوظ کر لی گئی ہے۔"


    def get_todays_live_summary(self):
        """آج کی حاضری کا خلاصہ (ڈیش بورڈ پر دکھانے کے لیے)۔
        - کلاس میں لگی حاضری کو ترجیح
        - نہیں تو ڈے حاضری دیکھتا ہے
        """
        if not self.institution:
            return {'total': 0, 'present_count': 0, 'absent': 0, 'late': 0, 'not_marked': 0, 'percentage': 0}
        
        today = dt_date.today()
        total_students = self.session.exec(
            select(func.count(Student.id)).where(
                Student.inst_id == self.institution.id,
                Student.is_active == True
            )
        ).one() or 0
        
        if total_students == 0:
            return {'total': 0, 'present_count': 0, 'absent': 0, 'late': 0, 'not_marked': 0, 'percentage': 0}
        
        # آج کے تمام سیشنز
        sessions = self.session.exec(
            select(ClassSession).where(ClassSession.date == today)
        ).all()
        session_ids = [s.id for s in sessions]
        
        # کلاس حاضری - پہلا ریکارڈ فی طالب علم
        explicit_att = {}
        if session_ids:
            att_records = self.session.exec(
                select(Attendance).where(
                    Attendance.inst_id == self.institution.id,
                    Attendance.session_id.in_(session_ids)
                )
            ).all()
            for a in att_records:
                if a.student_id not in explicit_att:
                    explicit_att[a.student_id] = a.status
        
        # ڈے حاضری (fallback)
        daily_att = self.session.exec(
            select(DailyAttendance).where(
                DailyAttendance.inst_id == self.institution.id,
                DailyAttendance.date == today
            )
        ).all()
        daily_map = {a.student_id: a.status for a in daily_att}
        
        # تمام طلبہ کی حتمی اسٹیٹس گنتی
        all_students = self.session.exec(
            select(Student.id).where(
                Student.inst_id == self.institution.id,
                Student.is_active == True
            )
        ).all()
        
        present_count = 0
        absent_count = 0
        late_count = 0
        
        for row in all_students:
            sid = row[0] if isinstance(row, tuple) else row
            status = explicit_att.get(sid) or daily_map.get(sid)
            if status == 'present':
                present_count += 1
            elif status == 'absent':
                absent_count += 1
            elif status == 'late':
                late_count += 1
        
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
        
        staff_stmt = select(func.count(Staff_Attendance.id), Staff_Attendance.status).where(
            Staff_Attendance.inst_id == self.institution.id,
            Staff_Attendance.date >= start_date,
            Staff_Attendance.date <= end_date
        ).group_by(Staff_Attendance.status)
        staff_res = self.session.exec(staff_stmt).all()
        
        return {
            'staff_summary': staff_res,
            'day_span': (end_date - start_date).days + 1,
            'no_records': False
        }

    def get_member_summary(self, member, days=30, course_id: Optional[int] = None) -> dict:
        """کسی ایک طالب علم یا ملازم کی حاضری کا مختصر خلاصہ - ڈے حاضری بھی شامل۔"""
        end_date = dt_date.today()
        start_date = end_date - timedelta(days=days-1)
        
        summary = {'present': 0, 'absent': 0, 'late': 0, 'excused': 0, 'total': 0}
        
        if isinstance(member, Student):
            admissions = self.session.exec(
                select(Admission).where(Admission.student_id == member.id, Admission.status == 'active')
            ).all()
            course_ids = [a.course_id for a in admissions]
            
            if course_id:
                course_ids = [course_id] if course_id in course_ids else []
            
            sessions = []
            if course_ids:
                sessions = self.session.exec(
                    select(ClassSession).where(
                        ClassSession.course_id.in_(course_ids),
                        ClassSession.date >= start_date,
                        ClassSession.date <= end_date
                    )
                ).all()
            
            session_ids = [s.id for s in sessions]
            
            # کلاس حاضری
            explicit_map = {}
            if session_ids:
                explicit_att = self.session.exec(
                    select(Attendance).where(
                        Attendance.student_id == member.id,
                        Attendance.session_id.in_(session_ids)
                    )
                ).all()
                explicit_map = {a.session_id: a.status for a in explicit_att}
            
            # ڈے حاضری
            daily_att = self.session.exec(
                select(DailyAttendance).where(
                    DailyAttendance.student_id == member.id,
                    DailyAttendance.date >= start_date,
                    DailyAttendance.date <= end_date
                )
            ).all()
            daily_map = {a.date: a.status for a in daily_att}
            
            # سیشن کی تاریخیں (ڈبل گنتی سے بچنا)
            session_covered_dates = set()
            
            for s in sessions:
                status = explicit_map.get(s.id) or daily_map.get(s.date)
                if status:
                    summary['total'] += 1
                    if status in summary:
                        summary[status] += 1
                session_covered_dates.add(s.date)
            
            # ان دنوں کی ڈے حاضری جب کوئی کلاس نہیں ہوئی
            for da in daily_att:
                if da.date not in session_covered_dates:
                    summary['total'] += 1
                    if da.status in summary:
                        summary[da.status] += 1
                    
        else:
            stmt = select(Staff_Attendance).where(
                Staff_Attendance.staff_member_id == member.id,
                Staff_Attendance.date >= start_date
            )
            records = self.session.exec(stmt).all()
            
            summary['total'] = len(records)
            for r in records:
                if r.status in summary:
                    summary[r.status] += 1
        
        summary['percentage'] = round((summary['present'] / summary['total'] * 100), 1) if summary['total'] > 0 else 0
        return summary

# Final end of file
