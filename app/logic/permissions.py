from fastapi import HTTPException
from sqlmodel import Session, select
from typing import Optional, Tuple

# Internal Imports
from ..models import Institution, User, Staff
from .roles import Role

class InstitutionAccess:
    """
    Centralized Permission Logic for Institution.
    (FastAPI/SQLModel Version)
    """

    PERMISSIONS_MAP = {
        'finance_manage': {
            Role.PRESIDENT.value, Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, Role.JOINT_SECRETARY.value,
            Role.ADMIN.value, Role.ACCOUNTANT.value
        },
        'academic_manage': {
            Role.PRESIDENT.value, Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, Role.JOINT_SECRETARY.value,
            Role.ADMIN.value, Role.ACADEMIC_HEAD.value
        },
        'academic_view': {
            Role.PRESIDENT.value, Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, Role.JOINT_SECRETARY.value,
            Role.COMMITTEE_MEMBER.value, Role.ADMIN.value, 
            Role.ACADEMIC_HEAD.value, Role.TEACHER.value, 
            Role.IMAM.value, Role.ACCOUNTANT.value
        },
        'staff_view': {
            Role.PRESIDENT.value, Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, Role.JOINT_SECRETARY.value,
            Role.COMMITTEE_MEMBER.value, Role.ADMIN.value, 
            Role.ACCOUNTANT.value
        }
    }

    def __init__(self, user: User, institution: Institution):
        self.user = user
        self.institution = institution
        
        self.is_auth = user is not None
        self.is_superuser = self.is_auth and getattr(user, 'is_superuser', False)
        self.is_owner = self.is_auth and (institution.user_id == user.id)
        
        # Resolve Staff Role
        self.staff_member = None
        self.staff_role = None
        
        #Note: In FastAPI logic, we should ideally fetch this once and pass it,
        # but for compatibility we'll check user object's relationships if available.
        if self.is_auth and not self.is_superuser:
            if hasattr(user, 'staff') and user.staff and user.staff.inst_id == institution.id:
                self.staff_member = user.staff
                self.staff_role = user.staff.role

    def _has_role_permission(self, permission_key: str) -> bool:
        allowed_roles = self.PERMISSIONS_MAP.get(permission_key, set())
        return self.staff_role in allowed_roles

    def can_manage_institution(self) -> bool:
        if not self.is_auth: return False
        if self.is_superuser or self.is_owner: return True
        return self.staff_role in {
            Role.ADMIN.value, Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value, Role.GENERAL_SECRETARY.value,
            Role.JOINT_SECRETARY.value
        }

    def can_view_staff(self) -> bool:
        if self.can_manage_institution(): return True
        return self._has_role_permission('staff_view')

    def can_manage_finance(self) -> bool:
        if self.can_manage_institution(): return True
        return self._has_role_permission('finance_manage')

    def can_manage_academics(self) -> bool:
        if self.can_manage_institution(): return True
        return self._has_role_permission('academic_manage')

    def can_view_academics(self) -> bool:
        if self.can_manage_academics(): return True
        return self._has_role_permission('academic_view')

    def enforce_finance_access(self, student_user=None):
        if student_user and student_user.id == self.user.id: return
        if not self.can_manage_finance():
            raise HTTPException(status_code=403, detail="Finance Access Denied: Only Admins or Accountants.")

    def enforce_academic_manage(self):
        if not self.can_manage_academics():
            raise HTTPException(status_code=403, detail="Restricted Access: Academic Management only.")
            
    def enforce_academic_view(self):
        if not self.can_view_academics():
            raise HTTPException(status_code=403, detail="Restricted Access: Academic Staff only.")

def get_institution_with_access(slug: str, session: Session, current_user: User, access_type: str = 'view') -> Tuple[Institution, InstitutionAccess]:
    """انسٹی ٹیوٹ لاتا ہے اور پرمیشن چیک کرتا ہے۔"""
    inst = session.exec(select(Institution).where(Institution.slug == slug)).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    access = InstitutionAccess(current_user, inst)

    # 1. Approval Check
    if not inst.is_approved and not access.is_superuser and not access.is_owner:
        raise HTTPException(status_code=403, detail="Institution Pending Approval")

    # 2. Permission Routing
    if access_type == 'admin':
        if not access.can_manage_institution(): raise HTTPException(status_code=403, detail="Admin Access Required.")
    elif access_type == 'finance':
        access.enforce_finance_access()
    elif access_type == 'academic_manage':
        access.enforce_academic_manage()
    elif access_type == 'academic_view':
        access.enforce_academic_view()
    elif access_type == 'staff_view':
        if not access.can_view_staff(): raise HTTPException(status_code=403, detail="Staff Access Required.")

    return inst, access