from sqlmodel import Session, select, func, desc, and_
from fastapi import HTTPException
from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Optional, List, Any
import json

# Import Models
from ..models import Institution, ClassSession, Income, Expense, Student, Staff, Course, Facility, Enrollment, Admission

class InstitutionManager:
    """Core logic layer for institution-level operations (Hyper-Complete Version)"""
    
    def __init__(self, user, session: Session, institution: Optional[Institution] = None):
        self.user = user
        self.session = session
        self.institution = institution
        
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = self.session.get(Institution, user.staff.inst_id)
            elif user:
                statement = select(Institution).where(Institution.user_id == user.id)
                self.institution = session.exec(statement).first()

    def _check_access(self):
        if not self.user: raise HTTPException(status_code=401)
        if getattr(self.user, 'is_superuser', False): return True
        if not self.institution: raise HTTPException(status_code=404)
        if self.user.id == self.institution.user_id: return True
        if hasattr(self.user, 'staff') and self.user.staff and self.user.staff.inst_id == self.institution.id:
            return True
        raise HTTPException(status_code=403)

    def get_dashboard_data(self):
        """ڈیش بورڈ کے لیے تمام ڈیٹا نکالنا (بشمول باریک سٹیٹسٹکس)۔"""
        self._check_access()
        from .finance import FinanceManager
        from .attendance import AttendanceManager
        from .roles import Role
        
        today = dt_date.today()
        
        # رول چیک برائے مالیات
        is_owner = self.institution.user_id == self.user.id
        staff = getattr(self.user, 'staff', None)
        is_admin = getattr(self.user, 'is_superuser', False) or is_owner or (staff and staff.role in [Role.ADMIN.value, Role.ACCOUNTANT.value])
        
        # 1. مالیاتی خلاصہ
        if is_admin:
            fm = FinanceManager(self.session, self.institution, self.user)
            finance = fm.institution_summary()
            analytics = fm.analytics()
            chart_data = analytics.get('chart_data', {})
        else:
            finance = {'revenue': {'total': 0}, 'total_expenses': 0, 'balance': 0}
            chart_data = {}
        
        # 2. حاضری اور سیشنز
        am = AttendanceManager(self.session, self.institution, self.user)
        attendance = am.get_todays_live_summary()
        
        recent_sessions = list(self.session.exec(
            select(ClassSession).join(Course).where(Course.inst_id == self.institution.id)
            .order_by(desc(ClassSession.date), desc(ClassSession.id)).limit(5)
        ))

        # 3. 🚀 باریک اعداد و شمار (جینگو کی طرح مکمل سٹیٹس)
        # اس مہینے کے نئے داخلوں کا حساب
        start_of_month = today.replace(day=1)
        new_students = self.session.exec(
            select(func.count(Student.id)).where(
                Student.inst_id == self.institution.id, 
                Student.admission_date >= start_of_month
            )
        ).one()

        stats = {
            'students': self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id, Student.is_active == True)).one(),
            'new_this_month': new_students,
            'staff': self.session.exec(select(func.count(Staff.id)).where(Staff.inst_id == self.institution.id, Staff.is_active == True)).one(),
            'courses': self.session.exec(select(func.count(Course.id)).where(Course.inst_id == self.institution.id, Course.is_active == True)).one(),
            'facilities': self.session.exec(select(func.count(Facility.id)).where(Facility.inst_id == self.institution.id)).one()
        }

        # 4. الرٹس
        alerts = self.get_quick_alerts()

        result = {
            'institution': self.institution,
            'is_admin': is_admin,
            'currency_label': self.get_currency_label(self.institution),
            'stats': stats,
            'finance': finance,
            'balance': finance.get('balance', 0),
            'total_expenses': finance.get('total_expenses', 0),
            'revenue': finance.get('revenue', {}).get('total', 0),
            'attendance': attendance,
            'recent_sessions': recent_sessions,
            'alerts': alerts,
            'today': today,
            'chart_data': {
                'labels': json.dumps(chart_data.get('labels', [])),
                'income': json.dumps(chart_data.get('income', [])),
                'expense': json.dumps(chart_data.get('expense', [])),
            },
        }
        return result

    def get_quick_alerts(self):
        """خودکار الرٹس۔"""
        from ..models import Fee
        overdue_subquery = select(func.count(Fee.id)).where(Fee.student_id == Student.id, Fee.status == 'overdue').scalar_subquery()
        defaulters = self.session.exec(select(Student).where(Student.inst_id == self.institution.id, overdue_subquery >= 3).limit(5)).all()
        
        # بھرے ہوئے کورسز کا چیک
        all_courses = self.session.exec(select(Course).where(Course.inst_id == self.institution.id, Course.is_active == True, Course.capacity > 0)).all()
        full_classes = []
        for c in all_courses:
            enrolled = self.session.exec(select(func.count(Enrollment.id)).where(Enrollment.course_id == c.id, Enrollment.status == 'active')).one()
            if enrolled >= (c.capacity * 0.9): full_classes.append(c)
            if len(full_classes) >= 5: break

        return {'defaulters': defaulters, 'full_classes': full_classes, 'count': len(defaulters) + len(full_classes)}

    @staticmethod
    def get_currency_label(institution=None):
        fallback = "Rs"
        if institution:
            for attr in ("currency_label", "currency_code", "currency"):
                value = getattr(institution, attr, None)
                if value: return str(value)
        return fallback
