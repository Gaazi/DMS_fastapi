from typing import List, Optional, Any, Dict, Tuple
from sqlmodel import Session, select, and_, or_
from datetime import time

# Models
from app.models import TimetableItem, Course, Staff, Facility, Institution

class ScheduleLogic:
    """ٹائم ٹیبل اور ہفتہ وار شیڈول مینیج کرنے کی لاجک (FastAPI/SQLModel Version)۔"""

    # ہفتے کے ایام کی میپنگ (Django logic transition)
    DAYS = [
        ('1', "Monday - پیر"), ('2', "Tuesday - منگل"), ('3', "Wednesday - بدھ"),
        ('4', "Thursday - جمعرات"), ('5', "Friday - جمعہ"), ('6', "Saturday - ہفتہ"),
        ('7', "Sunday - اتوار")
    ]

    def __init__(self, user: Any, session: Session, institution: Optional[Institution] = None):
        self.user = user
        self.session = session
        self.institution = institution
        
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = session.get(Institution, user.staff.inst_id)
            else:
                self.institution = session.exec(select(Institution).where(Institution.user_id == user.id)).first()

    def get_weekly_matrix(self, course_id: Optional[int] = None, staff_id: Optional[int] = None):
        """ہفتہ وار ٹائم ٹیبل کو ایک گرڈ (Grid) کی شکل میں تیار کرنا۔"""
        if not self.institution: return {}

        stmt = select(TimetableItem).where(
            TimetableItem.inst_id == self.institution.id,
            TimetableItem.is_active == True
        )
        if course_id:
            stmt = stmt.where(TimetableItem.course_id == course_id)
        if staff_id:
            stmt = stmt.where(TimetableItem.teacher_id == staff_id)
            
        items = self.session.exec(stmt.order_by(TimetableItem.start_time)).all()
        
        # ہفتے کے سات دنوں کے لیے خالی ڈکشنری
        matrix = {day: [] for day, label in self.DAYS}
        
        for item in items:
            if item.day_of_week in matrix:
                matrix[item.day_of_week].append(item)
            
        return matrix

    def check_conflict(self, day: str, start: time, end: time, teacher_id: Optional[int] = None, facility_id: Optional[int] = None):
        """چیک کرنا کہ کیا اس وقت استاد یا کلاس روم پہلے سے مصروف تو نہیں (Conflict Check)۔"""
        # ٹائم رینج میں اوورلیپ (Time Overlap) چیک کریں
        stmt = select(TimetableItem).where(
            TimetableItem.inst_id == self.institution.id,
            TimetableItem.day_of_week == day,
            TimetableItem.is_active == True,
            TimetableItem.start_time < end,
            TimetableItem.end_time > start
        )
        conflicts = self.session.exec(stmt).all()
        
        if teacher_id:
            if any(c.teacher_id == teacher_id for c in conflicts):
                return True, "استاد اس وقت پہلے ہی کسی اور کلاس میں مصروف ہیں۔"
        
        if facility_id:
            if any(c.facility_id == facility_id for c in conflicts):
                return True, "یہ کمرہ/ہال اس وقت پہلے ہی استعمال میں ہے۔"
                
        return False, None

    def get_schedule_context(self, course_id: Optional[int] = None):
        """ٹائم ٹیبل کے صفحے کے لیے ڈیٹا۔"""
        matrix = self.get_weekly_matrix(course_id=course_id)
        
        stmt_courses = select(Course).where(Course.inst_id == self.institution.id, Course.is_active == True)
        courses = self.session.exec(stmt_courses).all()
        
        stmt_staff = select(Staff).where(Staff.inst_id == self.institution.id, Staff.is_active == True)
        staff = self.session.exec(stmt_staff).all()
        
        return {
            "matrix": matrix,
            "courses": courses,
            "staff_members": staff,
            "days": self.DAYS,
            "selected_course": course_id
        }

