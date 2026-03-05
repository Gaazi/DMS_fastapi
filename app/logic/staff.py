from typing import List, Optional, Any, Dict
from sqlmodel import Session, select, func, desc, and_, or_
from fastapi import HTTPException
from datetime import date as dt_date, datetime
from decimal import Decimal
import calendar

# Models
from app.models import Institution, Staff, Staff_Attendance, StaffAdvance
from app.logic.audit import AuditLogic

class StaffLogic:
    """Business logic for Staff members, payroll, and recruitment (FastAPI/SQLModel Version)"""
    
    def __init__(self, user, session: Session, target: Any = None, institution: Optional[Institution] = None):
        """یوزر، سیشن، ادارے یا کسی مخصوص اسٹاف ممبر کے ساتھ مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        
        if isinstance(target, Institution):
            self.institution = target
            self.staff = None
        elif isinstance(target, Staff):
            self.staff = target
            self.institution = self.session.get(Institution, target.inst_id)
        else:
            self.staff = None
            self.institution = institution

        # Fallback resolution for institution
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = self.session.get(Institution, user.staff.inst_id)
            else:
                statement = select(Institution).where(Institution.user_id == user.id)
                self.institution = session.exec(statement).first()

    def _check_access(self):
        """چیک کرنا کہ کیا یوزر کو اسٹاف مینیجمنٹ اور تنخواہوں کے ریکارڈ تک رسائی حاصل ہے۔"""
        from app.logic.roles import Role
        
        if not self.user:
            raise HTTPException(status_code=401, detail="Authentication required.")
            
        if getattr(self.user, 'is_superuser', False):
            return True
            
        if not self.institution:
             raise HTTPException(status_code=404, detail="Institution context not found.")

        is_owner = (self.user.id == self.institution.user_id)
        staff = getattr(self.user, 'staff', None)
        
        # 1. Admin/Owner check
        if is_owner or (staff and staff.inst_id == self.institution.id and staff.role == Role.ADMIN.value):
            return True
            
        # 2. Accountant check (View access)
        if staff and staff.inst_id == self.institution.id and staff.role == Role.ACCOUNTANT.value:
            return True
            
        raise HTTPException(status_code=403, detail="Access denied to staff management.")

    def calculate_payroll(self, month: int, year: int, bonus: Decimal = Decimal('0.00')):
        """حاضری، غیر حاضری اور لیٹ آمد کی بنیاد پر ماہانہ تنخواہ کا حساب کتاب کرنا۔"""
        if not self.staff:
            return None
            
        # Attendance Data
        start_date = dt_date(year, month, 1)
        end_date = dt_date(year, month, calendar.monthrange(year, month)[1])
        
        attendance_stmt = select(Staff_Attendance).where(
            Staff_Attendance.staff_member_id == self.staff.id,
            Staff_Attendance.date >= start_date,
            Staff_Attendance.date <= end_date
        )
        attendance_records = self.session.exec(attendance_stmt).all()
        
        absent_days = len([r for r in attendance_records if r.status == 'absent'])
        late_days = len([r for r in attendance_records if r.is_late])
        
        base_salary = self.staff.base_salary or Decimal('0.00')
        days_in_month = (end_date - start_date).days + 1
        
        # Salary per day
        per_day = base_salary / Decimal(str(days_in_month))

        # 1. Absence Deduction
        absence_deduction = Decimal(str(absent_days)) * per_day
        
        # 2. Late Deduction (Half day salary for every 3 late arrivals)
        late_deduction = Decimal(str(late_days // 3)) * (per_day / 2)
        
        # 3. Advance Deduction
        advance_stmt = select(func.sum(StaffAdvance.amount)).where(
            StaffAdvance.staff_id == self.staff.id,
            StaffAdvance.is_adjusted == False
        )
        total_advance = self.session.exec(advance_stmt).one() or Decimal('0.00')
        total_advance = Decimal(str(total_advance))

        final_payable = (base_salary + bonus) - (absence_deduction + late_deduction + total_advance)
        
        return {
            'base': base_salary,
            'bonus': bonus,
            'deductions': {
                'absence': absence_deduction,
                'late': late_deduction,
                'advance': total_advance,
                'total': absence_deduction + late_deduction + total_advance
            },
            'final': max(Decimal('0.00'), final_payable).quantize(Decimal('1.00')),
            'attendance': {'absent': absent_days, 'late': late_days}
        }

    def process_salary(self, month: int, year: int, bonus: Decimal = Decimal('0.00')):
        """کسی ملازم کی تنخواہ کو حتمی شکل دینا اور اسے مالیاتی ریکارڈ (Expense) میں درج کرنا۔"""
        self._check_access()
        stats = self.calculate_payroll(month, year, bonus)
        
        from app.logic.finance import FinanceLogic
        fm = FinanceLogic(self.session, self.institution, self.user)
        
        # ریکارڈ ایکسپینس لیول فنکشن استعمال کریں
        desc_text = f"Salary for {self.staff.name} - {month}/{year}"
        expense = fm.record_expense(
            category="salary",
            amount=stats['final'],
            description=desc_text,
            date=dt_date.today()
        )
        
        # سابقہ ایڈوانس رقوم کو "Adjusted" (کٹوت شدہ) کے طور پر مارک کریں
        advances = self.session.exec(select(StaffAdvance).where(
            StaffAdvance.staff_id == self.staff.id, 
            StaffAdvance.is_adjusted == False
        )).all()
        for adv in advances:
            adv.is_adjusted = True
            self.session.add(adv)
            
        AuditLogic.log_activity(self.session, self.institution.id, self.user.id, 'process_salary', 'Staff', self.staff.id, self.staff.name, stats)
        self.session.commit()
        return True, "Salary has been processed and recorded.", stats

    def save_staff(self, data: dict):
        """نئے ملازم کا اندراج کرنا یا موجودہ کو اپڈیٹ کرنا۔"""
        self._check_access()
        staff_id = data.get('id')
        if staff_id:
            staff = self.session.get(Staff, staff_id)
            if not staff: raise HTTPException(status_code=404, detail="Staff not found")
            for k, v in data.items(): 
                if hasattr(staff, k): setattr(staff, k, v)
            action = "update"
        else:
            # Generate reg_id for Staff
            if not data.get('reg_id'):
                inst_prefix = (self.institution.reg_id or self.institution.slug[:3] or "INST").upper()
                inst_id_padded = f"{self.institution.id:03d}"
                staff_count = self.session.exec(select(func.count(Staff.id)).where(Staff.inst_id == self.institution.id)).one()
                serial = staff_count + 1
                data['reg_id'] = f"{inst_prefix}-{inst_id_padded}-E-{serial}"
                
                # Double check for reg_id uniqueness in this institution & increment serial if collision
                while self.session.exec(select(Staff).where(Staff.inst_id == self.institution.id, Staff.reg_id == data['reg_id'])).first():
                    serial += 1
                    data['reg_id'] = f"{inst_prefix}-{inst_id_padded}-E-{serial}"

            staff = Staff(**data)
            staff.inst_id = self.institution.id
            self.session.add(staff)
            action = "create"
        
        AuditLogic.log_activity(self.session, self.institution.id, self.user.id, action, 'Staff', staff.id, staff.name, data)
        self.session.commit()
        self.session.refresh(staff)
        return True, "Staff information has been saved successfully.", staff


    def process_bulk_payroll(self, month: int, year: int):
        """پورے ادارے کے تمام فعال ملازمین کی تنخواہوں کا ایک ساتھ حساب لگانا۔"""
        self._check_access()
        if not self.institution: return []
        
        members = self.session.exec(select(Staff).where(
            Staff.inst_id == self.institution.id, 
            Staff.is_active == True
        ).order_by(Staff.name)).all()
        
        results = []
        for member in members:
            # نئی انسٹی ٹینس یہاں بنائیں
            mgr = StaffLogic(self.user, self.session, target=member)
            results.append({
                'staff': member,
                'report': mgr.calculate_payroll(month, year)
            })
        return results

    def execute_bulk_payroll(self, month: int, year: int):
        """تمام فعال ملازمین کی تنخواہیں ایک ساتھ پراسیس کرنا اور ان کے اخراجات درج کرنا۔"""
        self._check_access()
        results = self.process_bulk_payroll(month, year)
        count = 0
        total = Decimal('0.00')
        
        for res in results:
            if res['report'] and res['report']['final'] > 0:
                member_manager = StaffLogic(self.user, self.session, target=res['staff'])
                member_manager.process_salary(month, year)
                count += 1
                total += res['report']['final']
        
        return True, f"{count} ارکان کی تنخواہیں کامیابی سے ریکارڈ کر دی گئی ہیں (کل رقم: {total})", count

    def record_advance(self, staff_id: int, amount: Decimal, adv_date: dt_date):
        """اسٹاف کو ایڈوانس رقم دینا۔"""
        self._check_access()
        advance = StaffAdvance(
            inst_id=self.institution.id,
            staff_id=staff_id,
            amount=amount,
            date=adv_date,
            is_adjusted=False
        )
        self.session.add(advance)
        self.session.commit()
        self.session.refresh(advance)
        AuditLogic.log_activity(self.session, self.institution.id, self.user.id, 'create_advance', 'StaffAdvance', advance.id, f"Advance for staff #{staff_id}", {'amount': float(amount)})
        return advance

    def get_advances(self, staff_id: Optional[int] = None):
        """ایڈوانس رقوم کی فہرست مع اسٹاف نام۔"""
        self._check_access()
        stmt = select(StaffAdvance, Staff.name.label("staff_name")).join(Staff, Staff.id == StaffAdvance.staff_id).where(StaffAdvance.inst_id == self.institution.id)
        if staff_id: stmt = stmt.where(StaffAdvance.staff_id == staff_id)
        results = self.session.exec(stmt.order_by(desc(StaffAdvance.date))).all()
        
        # Convert to list of dicts or objects with name attached
        advances = []
        for adv, name in results:
            setattr(adv, "staff_name", name)
            advances.append(adv)
        return advances

    def get_staff_list(self, q: Optional[str] = None, role: Optional[str] = None):
        """اسٹاف کارڈز کے لیے ڈیٹا مہیا کرنا مع حاضری۔"""
        self._check_access()
        stmt = select(Staff).where(Staff.inst_id == self.institution.id)
        if q:
            stmt = stmt.where(or_(Staff.name.contains(q), Staff.mobile.contains(q)))
        if role:
            stmt = stmt.where(Staff.role == role)
        
        members = self.session.exec(stmt.order_by(Staff.name)).all()
        today = dt_date.today()
        start_of_month = today.replace(day=1)
        
        for m in members:
            # Presents
            presents = self.session.exec(select(func.count(Staff_Attendance.id)).where(
                Staff_Attendance.staff_member_id == m.id,
                Staff_Attendance.status == 'present',
                Staff_Attendance.date >= start_of_month
            )).one()
            
            # Absents
            absents = self.session.exec(select(func.count(Staff_Attendance.id)).where(
                Staff_Attendance.staff_member_id == m.id,
                Staff_Attendance.status == 'absent',
                Staff_Attendance.date >= start_of_month
            )).one()

            m.month_presents = presents
            m.month_absents = absents
            # Defaults for finance fields to prevent template errors
            m.has_pending_salary = False 
            m.month_due_amount = Decimal("0.00")
            
        return members

    def get_list_context(self, q=None, role=None) -> dict:
        """Staff list page کا مکمل context — members + stats۔"""
        members = self.get_staff_list(q=q, role=role)
        return {
            "staff_members": members,
            "total_count": len(members),
            "active_count": sum(1 for m in members if m.is_active),
            "query": q,
            "role": role,
        }

    def get_payroll_stats(self, month: int, year: int) -> list:
        """Payroll report page کے لیے تمام staff کی تنخواہوں کا حساب۔"""
        return self.process_bulk_payroll(month, year)

    def promote_student_to_staff(self, student, institution, request_url_for):
        """طالب علم کو staff میں promote کریں۔ (redirect URL, is_new) واپس کرتا ہے۔"""
        from datetime import date as dt
        # Duplicate check
        existing = None
        if student.mobile:
            existing = self.session.exec(
                select(Staff).where(Staff.inst_id == institution.id, Staff.mobile == student.mobile)
            ).first()
        if not existing:
            existing = self.session.exec(
                select(Staff).where(Staff.inst_id == institution.id, Staff.name == student.full_name)
            ).first()

        if existing:
            return request_url_for("dms_staff_edit", staff_id=existing.id) + "?msg=already_staff", False

        new_staff = Staff(
            inst_id=institution.id,
            name=student.full_name,
            mobile=student.mobile or "",
            email=getattr(student, "email", "") or "",
            address=getattr(student, "address", "") or "",
            role="volunteer",
            base_salary=0.0,
            hire_date=dt.today(),
            is_active=True,
        )
        self.session.add(new_staff)
        self.session.commit()
        self.session.refresh(new_staff)
        return request_url_for("dms_staff_edit", staff_id=new_staff.id) + "?msg=promoted", True
