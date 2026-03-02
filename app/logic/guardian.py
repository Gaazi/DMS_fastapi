from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
# Models
from ..models import Student, Attendance, Fee, Institution, Parent, ClassSession

class GuardianManager:
    """Business logic and security for the Guardian/Parent dashboard (FastAPI/SQLModel Version)"""
    
    def __init__(self, session: Session, user: Any, institution: Optional[Institution] = None):
        """یوزر اور سیشن کے ساتھ سرپرست (Guardian) مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        self.institution = institution
        
        # Resolve Parent Profile
        self.parent = self.session.exec(select(Parent).where(Parent.user_id == user.id)).first()
        
        if not self.institution and self.parent:
            self.institution = self.session.get(Institution, self.parent.inst_id)

    def _check_access(self):
        """والدین کی رسائی کو یقینی بنانے کا طریقہ۔"""
        if not self.user: raise HTTPException(status_code=401, detail="Authentication required.")
        if not self.parent and not getattr(self.user, 'is_superuser', False):
             if not (self.institution and self.user.id == self.institution.user_id):
                 raise HTTPException(status_code=403, detail="Access denied.")
        return True

    def get_dashboard_context(self):
        """والدین کے ڈیش بورڈ کے لیے ان کے بچوں کی حاضری اور فیس کا مکمل ڈیٹا اکٹھا کرنا۔"""
        self._check_access()
        
        # 2. Student Query Logic
        if self.parent:
            # اس سرپرست کے زیر سایہ تمام طالب علموں کو تلاش کریں
            stmt = select(Student).where(Student.parent_id == self.parent.id)
            students = self.session.exec(stmt).all()
        else:
            # مالکان یا سپر یوزر کے لیے تمام طالب علم (اگر ادارہ معلوم ہو)
            if not self.institution: return {}
            stmt = select(Student).where(Student.inst_id == self.institution.id)
            students = self.session.exec(stmt).all()

        student_ids = [s.id for s in students]
        if not student_ids:
            return {"parent": self.parent, "institution": self.institution, "students": [], "attendance": [], "fees": [], "total_due": 0, "total_paid": 0}

        # 3. Attendance Logic (Last 10 records)
        att_stmt = select(Attendance).join(ClassSession).where(Attendance.student_id.in_(student_ids)).order_by(desc(ClassSession.date)).limit(10)
        attendance = self.session.exec(att_stmt).all()
        
        # 4. Fee Logic (Last 10 records)
        fee_stmt = select(Fee).where(Fee.student_id.in_(student_ids)).order_by(desc(Fee.due_date)).limit(10)
        fees = self.session.exec(fee_stmt).all()
        
        # 5. Aggregate Totals
        totals_stmt = select(
            func.sum(Fee.amount_due),
            func.sum(Fee.amount_paid)
        ).where(Fee.student_id.in_(student_ids))
        
        totals_res = self.session.exec(totals_stmt).first()
        due, paid = totals_res if totals_res else (0, 0)
        
        return {
            "parent": self.parent,
            "institution": self.institution,
            "students": students,
            "attendance": attendance,
            "fees": fees,
            "total_due": due or 0,
            "total_paid": paid or 0,
        }


