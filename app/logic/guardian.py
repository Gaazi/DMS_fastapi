from typing import Optional, Any
from sqlmodel import Session, select, func, desc
from fastapi import HTTPException
from datetime import date as dt_date

# Models
from app.models import Student, Attendance, Fee, Institution, Parent, ClassSession
from app.models.attendance import DailyAttendance
from app.models.links import StudentParentLink


class GuardianManager:
    """Business logic and security for the Guardian/Parent dashboard (FastAPI/SQLModel Version)"""

    def __init__(self, session: Session, user: Any, institution: Optional[Institution] = None):
        """یوزر اور سیشن کے ساتھ سرپرست (Guardian) مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        self.institution = institution

        # Resolve Parent Profile via user_id
        self.parent = self.session.exec(
            select(Parent).where(Parent.user_id == user.id)
        ).first() if user else None

        if not self.institution and self.parent:
            self.institution = self.session.get(Institution, self.parent.inst_id)

    def _check_access(self):
        """والدین کی رسائی کو یقینی بنانے کا طریقہ۔"""
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not self.parent and not getattr(self.user, 'is_superuser', False):
            if not (self.institution and self.user.id == self.institution.user_id):
                raise HTTPException(status_code=403, detail="No guardian profile linked to this account.")
        return True

    def get_dashboard_context(self):
        """والدین کے ڈیش بورڈ کے لیے ان کے بچوں کی حاضری اور فیس کا مکمل ڈیٹا اکٹھا کرنا۔"""
        self._check_access()

        today = dt_date.today()
        start_of_month = today.replace(day=1)

        # 1. طالب علموں کی تلاش (StudentParentLink کے ذریعے)
        if self.parent:
            link_stmt = select(Student).join(
                StudentParentLink, StudentParentLink.student_id == Student.id
            ).where(
                StudentParentLink.parent_id == self.parent.id
            )
            students = list(self.session.exec(link_stmt).all())

            # Fallback: براہ راست relationship
            if not students and hasattr(self.parent, 'students'):
                students = list(self.parent.students)
        else:
            if not self.institution:
                return {}
            students = list(self.session.exec(
                select(Student).where(Student.inst_id == self.institution.id)
            ).all())

        student_ids = [s.id for s in students]

        if not student_ids:
            return {
                "parent": self.parent,
                "institution": self.institution,
                "students": [],
                "attendance": [],
                "fees": [],
                "total_due": 0,
                "total_paid": 0,
                "total_balance": 0,
                "total_pending_fees": 0,
                "today": today,
            }

        # 2. حاضری — آخری 15 ریکارڈز
        attendance = list(self.session.exec(
            select(Attendance)
            .join(ClassSession)
            .where(Attendance.student_id.in_(student_ids))
            .order_by(desc(ClassSession.date))
            .limit(15)
        ).all())

        # 3. فیسیں — آخری 15
        fees = list(self.session.exec(
            select(Fee)
            .where(Fee.student_id.in_(student_ids))
            .order_by(desc(Fee.due_date))
            .limit(15)
        ).all())

        # 4. مالیاتی خلاصہ
        total_due = self.session.exec(
            select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount)).where(
                Fee.student_id.in_(student_ids),
                Fee.status != 'Cancelled'
            )
        ).one() or 0

        total_paid = self.session.exec(
            select(func.sum(Fee.amount_paid)).where(
                Fee.student_id.in_(student_ids)
            )
        ).one() or 0

        total_pending_fees = self.session.exec(
            select(func.count(Fee.id)).where(
                Fee.student_id.in_(student_ids),
                Fee.status.in_(['Pending', 'Partial'])
            )
        ).one() or 0

        # 5. ہر طالب علم کے لیے اس ماہ کی حاضری اور بقایا فیس
        for s in students:
            class_present = self.session.exec(
                select(func.count(Attendance.id)).join(ClassSession).where(
                    Attendance.student_id == s.id,
                    Attendance.status == 'present',
                    ClassSession.date >= start_of_month
                )
            ).one() or 0

            day_present = self.session.exec(
                select(func.count(DailyAttendance.id)).where(
                    DailyAttendance.student_id == s.id,
                    DailyAttendance.status == 'present',
                    DailyAttendance.date >= start_of_month
                )
            ).one() or 0

            s_due = self.session.exec(
                select(func.sum(Fee.amount_due + Fee.late_fee - Fee.discount - Fee.amount_paid)).where(
                    Fee.student_id == s.id,
                    Fee.status.in_(['Pending', 'Partial'])
                )
            ).one() or 0

            object.__setattr__(s, '_month_present', class_present + day_present)
            object.__setattr__(s, '_pending_due', float(s_due))

        return {
            "parent": self.parent,
            "institution": self.institution,
            "students": students,
            "attendance": attendance,
            "fees": fees,
            "total_due": float(total_due),
            "total_paid": float(total_paid),
            "total_balance": float(total_due) - float(total_paid),
            "total_pending_fees": total_pending_fees,
            "today": today,
        }
