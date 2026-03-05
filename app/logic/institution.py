from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Optional, List, Any
import json

# Import Models
from app.models import Institution, ClassSession, Income, Expense, Student, Staff, Parent, Course, Facility, Enrollment, Admission

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
        from app.logic.finance import FinanceManager
        from app.logic.attendance import AttendanceManager
        from app.logic.roles import Role
        
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
            .order_by(desc(ClassSession.date), desc(ClassSession.id)).limit(10)
        ))

        # 3. 🚀 باریک اعداد و شمار (جینگو کی طرح مکمل سٹیٹس)
        # اس مہینے کے نئے داخلوں کا حساب
        start_of_month = today.replace(day=1)
        new_students_count = self.session.exec(
            select(func.count(Student.id)).where(
                Student.inst_id == self.institution.id, 
                Student.admission_date >= start_of_month
            )
        ).one()

        active_students_count = self.session.exec(select(func.count(Student.id)).where(Student.inst_id == self.institution.id, Student.is_active == True)).one()
        active_staff_count = self.session.exec(select(func.count(Staff.id)).where(Staff.inst_id == self.institution.id, Staff.is_active == True)).one()
        active_courses_count = self.session.exec(select(func.count(Course.id)).where(Course.inst_id == self.institution.id, Course.is_active == True)).one()
        facilities_count = self.session.exec(select(func.count(Facility.id)).where(Facility.inst_id == self.institution.id)).one()

        stats = {
            'students': active_students_count,
            'new_this_month': new_students_count,
            'staff': active_staff_count,
            'courses': active_courses_count,
            'facilities': facilities_count
        }

        # Recent Items for Sidebar/Lists
        recent_students = self.session.exec(select(Student).where(Student.inst_id == self.institution.id).order_by(desc(Student.id)).limit(5)).all()
        recent_staff = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id).order_by(desc(Staff.id)).limit(5)).all()

        # 4. الرٹس
        alerts = self.get_quick_alerts()

        result = {
            'institution': self.institution,
            'is_admin': is_admin,
            'can_view_academics': True, # Explicitly for template logic
            'is_staff_admin': is_admin,
            'is_dms_admin': is_admin,
            'currency_label': self.get_currency_label(self.institution),
            'stats': stats,
            'finance': finance,
            'balance': finance.get('balance', 0),
            'total_expenses': finance.get('total_expenses', 0),
            'total_donations': finance.get('total_amount', 0), # Match template
            'revenue': finance.get('revenue', {}).get('total', 0),
            'attendance': attendance,
            'today_attendance': attendance.get('present_count', 0), # Match template
            'recent_sessions': recent_sessions,
            'recent_students': recent_students,
            'recent_staff': recent_staff,
            'alerts': alerts,
            'today': today,
            'total_records': active_students_count + active_staff_count + active_courses_count + facilities_count,
            'chart_data': {
                'labels': json.dumps(chart_data.get('labels', [])),
                'income': json.dumps(chart_data.get('income', [])),
                'expense': json.dumps(chart_data.get('expense', [])),
            },
        }
        return result

    def get_quick_alerts(self):
        """خودکار الرٹس۔"""
        from app.models import Fee
        from datetime import date as dt_date_now
        today_now = dt_date_now.today()
        # Find students with multiple pending fees where due date has passed
        overdue_subquery = select(func.count(Fee.id)).where(
            Fee.student_id == Student.id, 
            Fee.status.in_(['Pending', 'Partial']),
            Fee.due_date < today_now
        ).scalar_subquery()
        defaulters = self.session.exec(select(Student).where(Student.inst_id == self.institution.id, overdue_subquery >= 2).limit(5)).all()
        
        # بھرے ہوئے کورسز کا چیک
        all_courses = self.session.exec(select(Course).where(Course.inst_id == self.institution.id, Course.is_active == True, Course.capacity > 0)).all()
        full_classes = []
        for c in all_courses:
            enrolled = self.session.exec(select(func.count(Enrollment.id)).where(Enrollment.course_id == c.id, Enrollment.status == 'active')).one()
            if enrolled >= (c.capacity * 0.9): full_classes.append(c)
            if len(full_classes) >= 5: break

        return {'defaulters': defaulters, 'full_classes': full_classes, 'count': len(defaulters) + len(full_classes)}

    def run_bulk_maintenance(self) -> dict:
        """بلک اپڈیٹ: تمام آئی ڈیز کو 'PREFIX-INST_ID-PERSON_TYPE-PERSON_ID' فارمیٹ (مثلاً MKT-001-S-0064) میں اپ ڈیٹ کرنا۔"""
        self._check_access()
        
        counts = {"students": 0, "staff": 0, "parents": 0, "slugs": 0}
        from app.logic.utils import generate_slug
        
        # 1. Institution Prefix and Padded ID
        inst_prefix = "GEN"
        if self.institution.reg_id and "-" in self.institution.reg_id:
            inst_prefix = self.institution.reg_id.split("-")[0].upper()
        elif self.institution.reg_id:
            inst_prefix = str(self.institution.reg_id)[:3].upper()
        elif self.institution.slug:
            inst_prefix = "".join([w[0] for w in self.institution.slug.split("-") if w])[:3].upper()
        
        inst_id_str = f"{self.institution.id:03d}"
        
        # Helper to format: PREFIX-INST_ID-TYPE-ID
        def format_id(p_prefix, p_id):
            return f"{inst_prefix}-{inst_id_str}-{p_prefix}-{p_id:04d}"

        # 1. Students
        students = self.session.exec(select(Student).where(Student.inst_id == self.institution.id)).all()
        for s in students:
            new_reg = format_id("S", s.id)
            if s.reg_id != new_reg:
                s.reg_id = new_reg
                self.session.add(s)
                counts["students"] += 1
            
            if not s.slug:
                s.slug = generate_slug(f"{s.name}-{s.id}")
                self.session.add(s)
                counts["slugs"] += 1
            
        # 2. Staff
        staff_members = self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id)).all()
        for st in staff_members:
            new_reg = format_id("E", st.id)
            if st.reg_id != new_reg:
                st.reg_id = new_reg
                self.session.add(st)
                counts["staff"] += 1
            
        # 3. Parents
        parents = self.session.exec(select(Parent).where(Parent.inst_id == self.institution.id)).all()
        for p in parents:
            new_reg = format_id("G", p.id)
            if p.reg_id != new_reg:
                p.reg_id = new_reg
                self.session.add(p)
                counts["parents"] += 1
            
        self.session.commit()
        return counts





    def _generate_unique_reg_id(self, model, prefix: str) -> str:
        """ادارے کے کوڈ اور رینڈم نمبر سے منفرد آئی ڈی بنانا۔"""
        # Institution Code
        inst_part = "GEN"
        if self.institution.reg_id:
            inst_part = str(self.institution.reg_id)[:3].upper()
        elif self.institution.slug:
            inst_part = "".join([w[0] for w in self.institution.slug.split("-") if w])[:3].upper()
            
        # Random numeric part
        from app.logic.utils import get_random_string
        import random
        
        while True:
            # Format: [INST]-[PREFIX][RANDOM] e.g. MKT-S1234
            num = random.randint(1000, 9999)
            candidate = f"{inst_part}-{prefix}{num}"
            
            # Check uniqueness
            exists = self.session.exec(select(model).where(model.inst_id == self.institution.id, model.reg_id == candidate)).first()
            if not exists:
                return candidate

    @staticmethod
    def get_currency_label(institution=None):
        fallback = "Rs"
        if institution:
            for attr in ("currency_label", "currency_code", "currency"):
                value = getattr(institution, attr, None)
                if value: return str(value)
        return fallback

