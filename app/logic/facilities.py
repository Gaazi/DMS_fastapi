from sqlmodel import Session, select, func
from typing import Optional, List
from fastapi import HTTPException

# Internal Imports
from app.models import Facility, Institution, User
from app.logic.audit import AuditLogic

class FacilityLogic:
    """Business logic for managing institution facilities and assets (SQLModel Version)"""
    
    def __init__(self, session: Session, user: User, institution: Optional[Institution] = None):
        """یوزر اور ادارے کی معلومات کے ساتھ سہولیات (Facilities) مینیجر کو شروع کرنا۔"""
        self.user = user
        self.session = session
        self.institution = institution
        
        if not self.institution:
            if hasattr(user, 'staff') and user.staff:
                self.institution = session.get(Institution, user.staff.inst_id)
            elif user:
                self.institution = session.exec(select(Institution).where(Institution.user_id == user.id)).first()

    def _check_access(self):
        """سیکیورٹی چیک: سہولیات کے ریکارڈز تک رسائی کے حقوق کی تصدیق۔"""
        if not self.user: raise HTTPException(status_code=401, detail="Authentication required.")
        if getattr(self.user, 'is_superuser', False): return True
        if not self.institution: raise HTTPException(status_code=400, detail="Institution context missing.")

        is_owner = (self.user.id == self.institution.user_id)
        is_staff = hasattr(self.user, 'staff') and self.user.staff and self.user.staff.inst_id == self.institution.id
        
        if not (is_owner or is_staff):
            raise HTTPException(status_code=403, detail="Access denied.")
        return True

    def get_all(self):
        """ادارے کی تمام دستیاب سہولیات کی فہرست حاصل کرنا۔"""
        if not self.institution: return []
        return self.session.exec(select(Facility).where(Facility.inst_id == self.institution.id).order_by(Facility.name)).all()

    def save_facility(self, data: dict):
        """نئی سہولت کا اندراج کرنا یا پہلے سے موجود ریکارڈ میں تبدیلی کرنا۔"""
        self._check_access()
        facility_id = data.get('id')
        if facility_id:
            facility = self.session.get(Facility, facility_id)
            if not facility or facility.inst_id != self.institution.id:
                raise HTTPException(status_code=404, detail="Facility not found.")
            for k, v in data.items():
                if hasattr(facility, k): setattr(facility, k, v)
            action = "update"
        else:
            facility = Facility(**data)
            facility.inst_id = self.institution.id
            self.session.add(facility)
            action = "create"
        
        self.session.flush()
        AuditLogic.log_activity(self.session, self.institution.id, self.user.id, action, 'Facility', facility.id or 0, facility.name, data)
        self.session.commit()
        self.session.refresh(facility)
        return True, "Facility information saved successfully.", facility

    def delete_facility(self, facility_id: int):
        """کسی مخصوص سہولت کے ریکارڈ کو حذف کرنا۔"""
        self._check_access()
        facility = self.session.get(Facility, facility_id)
        if not facility or facility.inst_id != self.institution.id:
            return False, "Record not found.", None
            
        name = facility.name
        AuditLogic.log_activity(self.session, self.institution.id, self.user.id, 'delete', 'Facility', facility_id, name, {})
        self.session.delete(facility)
        self.session.commit()
        return True, f"Facility '{name}' deleted.", None


    def get_list_context(self, edit_id: Optional[int] = None):
        """تیاری: سہولیات کی فہرست کا سیاق و سباق۔"""
        self._check_access()
        
        editing_facility = None
        if edit_id:
            editing_facility = self.session.get(Facility, edit_id)
        
        facilities = self.get_all()
        available_count = len([f for f in facilities if f.is_available])
        types_count = len({f.facility_type for f in facilities})

        return {
            "institution": self.institution,
            "facilities": facilities,
            "editing_facility": editing_facility,
            "available_count": available_count,
            "facility_types_count": types_count
        }

