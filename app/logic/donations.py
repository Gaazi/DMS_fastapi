from sqlmodel import Session, select, func, desc
from typing import Optional, List, Tuple, Any
from datetime import datetime, date
from fastapi import HTTPException

# Internal Imports
# Internal Imports
from ..models import Income, Donor, Institution, User
from .audit import AuditManager

class DonationManager:
    """Business logic for managing institution income and donors (SQLModel Version)"""
    
    def __init__(self, session: Session, user: User, institution: Optional[Institution] = None):
        """یوزر اور ادارے کی معلومات کے ساتھ ڈونیشن مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        self.institution = institution
        
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = session.get(Institution, user.staff.inst_id)
            elif user:
                self.institution = session.exec(select(Institution).where(Institution.user_id == user.id)).first()

    def _check_access(self):
        """سیکیورٹی چیک۔"""
        if not self.user: raise HTTPException(status_code=401, detail="Authentication required.")
        return True

    def get_detailed_summary(self):
        """آمدنی کا تفصیلی خلاصہ۔"""
        self._check_access()
        # Stats aggregation
        stats_stmt = select(
            func.sum(Income.amount),
            func.count(Income.id),
            func.avg(Income.amount)
        ).where(Income.inst_id == self.institution.id)
        
        res = self.session.exec(stats_stmt).first()
        total, count, avg = res if res else (0, 0, 0)
        
        latest = self.session.exec(
            select(Income).where(Income.inst_id == self.institution.id).order_by(desc(Income.date), desc(Income.id))
        ).first()
        
        return {
            'total_amount': total or 0,
            'donation_count': count or 0,
            'average_amount': avg or 0,
            'latest_donation': latest
        }

    def record_donation(self, amount: float, donor_id: Optional[int] = None, source: str = "Donation", description: str = ""):
        """عطیہ کا اندراج کرنا۔"""
        self._check_access()
        income = Income(
            inst_id=self.institution.id,
            donor_id=donor_id,
            amount=amount,
            date=date.today(),
            source=source,
            description=description
        )
        self.session.add(income)
        self.session.flush()
        
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'record_donation', 'Income', income.id or 0, f"Donation of {amount}", {})
        self.session.commit()
        self.session.refresh(income)
        return income

    def get_or_create_donor(self, data: dict):
        """ڈونر تلاش کرنا یا بنانا۔"""
        self._check_access()
        name = data.get('name')
        phone = data.get('phone', '')
        
        donor = self.session.exec(
            select(Donor).where(Donor.inst_id == self.institution.id, Donor.name == name, Donor.phone == phone)
        ).first()
        
        if not donor:
            donor = Donor(inst_id=self.institution.id, **data)
            self.session.add(donor)
            self.session.flush()
            AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'create', 'Donor', donor.id or 0, donor.name, data)
            self.session.commit()
            self.session.refresh(donor)
            return True, "نیا ڈونر رجسٹر کر دیا گیا ہے۔", donor
        
        return True, "ڈونر پہلے سے موجود ہے۔", donor

    def update_donor(self, donor_id: int, data: dict):
        """ڈونر کی معلومات میں ترمیم۔"""
        self._check_access()
        donor = self.session.get(Donor, donor_id)
        if not donor or donor.inst_id != self.institution.id:
            raise HTTPException(status_code=404, detail="Donor not found.")
            
        for k, v in data.items():
            if hasattr(donor, k): setattr(donor, k, v)
        
        self.session.add(donor)
        AuditManager.log_activity(self.session, self.institution.id, self.user.id, 'update', 'Donor', donor.id, donor.name, data)
        self.session.commit()
        return True

    def handle_public_donation(self, data: dict):
        """عوام کی طرف سے براہ راست عطیہ۔"""
        # (بغیر یوزر کے بھی کام کرے گا)
        # Note: self.user can be None here
        donor_data = {
            'name': data.get('donor_name'),
            'phone': data.get('donor_phone'),
            'email': data.get('donor_email')
        }
        
        # ڈونر ڈھونڈیں یا بنائیں (اس لاجک کے لیے ہم عارضی طور پر سیکیورٹی پیرا میٹر نظر انداز کر سکتے ہیں)
        name = donor_data['name']
        donor = self.session.exec(select(Donor).where(Donor.inst_id == self.institution.id, Donor.name == name)).first()
        if not donor:
            donor = Donor(inst_id=self.institution.id, **donor_data)
            self.session.add(donor)
            self.session.flush()

        income = Income(
            inst_id=self.institution.id,
            donor_id=donor.id,
            amount=float(data.get('amount', 0)),
            date=date.today(),
            source="Public Donation",
            description=data.get('notes', '')
        )
        self.session.add(income)
        self.session.commit()
        return True, "عطیہ وصول کر لیا گیا ہے۔ جزاک اللہ!", income

    def get_donor_analytics(self, donor: Donor):
        """کسی مخصوص ڈونر کی طرف سے دی گئی کل رقم اور اس کی تاریخ کا تجزیہ۔"""
        self._check_access()
        donations = self.session.exec(select(Income).where(Income.donor_id == donor.id).order_by(desc(Income.date))).all()
        total = sum([d.amount for d in donations])
        
        return {
            "donor": donor,
            "donations": donations,
            "total_donated": total
        }

    def get_top_donors(self, limit=5):
        """سب سے زیادہ مالی تعاون کرنے والے نمایاں ڈونرز کی فہرست۔"""
        self._check_access()
        # SQLModel / SQLAlchemy group by query
        stmt = select(
            Donor, 
            func.sum(Income.amount).label("total"), 
            func.count(Income.id).label("count")
        ).join(Income).where(Income.inst_id == self.institution.id).group_by(Donor.id).order_by(desc("total")).limit(limit)
        
        results = self.session.exec(stmt).all()
        
        donors = []
        for d, total, count in results:
            d.total_donated = total
            d.donation_count = count
            donors.append(d)
        return donors

    def get_donation_list_context(self, page=1, page_size=20):
        """عطیات کی فہرست والے صفحے کے لیے ڈیٹا اور صفحہ بندی (Pagination) تیار کرنا۔"""
        self._check_access()
        page = int(page) if page else 1
        
        query = select(Income).where(Income.inst_id == self.institution.id).order_by(desc(Income.date), desc(Income.id))
        
        # Pagination
        offset = (page - 1) * page_size
        donations = self.session.exec(query.offset(offset).limit(page_size)).all()
        total_count = self.session.exec(select(func.count(Income.id)).where(Income.inst_id == self.institution.id)).one()
        
        # Stats
        stats_stmt = select(func.sum(Income.amount), func.avg(Income.amount)).where(Income.inst_id == self.institution.id)
        res = self.session.exec(stats_stmt).first()
        total, avg = res if res else (0, 0)
        
        donors = self.session.exec(select(Donor).where(Donor.inst_id == self.institution.id)).all()
        
        return {
            "donations": donations,
            "total_donations": total or 0,
            "average_donation": avg or 0,
            "donation_count": total_count or 0,
            "donors": donors,
            "has_next": (offset + page_size) < total_count,
            "has_prev": page > 1,
            "next_page": page + 1,
            "prev_page": page - 1,
            "current_page": page
        }

    def get_donor_list_context(self, page=1, page_size=50):
        """ادارے کے تمام عطیہ دہندگان (Donors) کی فہرست اور ان کا خلاصہ۔"""
        self._check_access()
        page = int(page) if page else 1
        
        query = select(Donor).where(Donor.inst_id == self.institution.id).order_by(Donor.name)
        
        # Pagination
        offset = (page - 1) * page_size
        donors = self.session.exec(query.offset(offset).limit(page_size)).all()
        total_count = self.session.exec(select(func.count(Donor.id)).where(Donor.inst_id == self.institution.id)).one()
        
        return {
            "donors": donors,
            "total_count": total_count,
            "has_next": (offset + page_size) < total_count,
            "has_prev": page > 1,
            "next_page": page + 1,
            "prev_page": page - 1,
            "current_page": page
        }

