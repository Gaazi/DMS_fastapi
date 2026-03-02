from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from ..models import Institution

# فرض کریں کہ آپ کے Roles یہاں ڈیفائن ہیں
# اگر آپ کے پاس یہ فائل نہیں، تو نیچے والی لائن کمنٹ کر کے Roles کو یہاں hardcode کر لیں
from ..logic.roles import Role 

class InstitutionAccess:
    """
    Centralized Permission Logic for Institution.
    یہ کلاس اجازتوں (Permissions) کو کنٹرول کرتی ہے اور کوڈ کو Scalable بناتی ہے۔
    """

    # -------------------------------------------------------------------
    # 1. Role Mappings (Scalability کے لیے سب سے اہم حصہ)
    # کل کو اگر نیا رول آئے تو صرف یہاں لسٹ میں شامل کریں، باقی کوڈ نہیں چھیڑنا۔
    # -------------------------------------------------------------------
    PERMISSIONS_MAP = {
        # مالیاتی انتظام (عہدیداران + خزانچی + ایڈمن)
        'finance_manage': {
            Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, 
            Role.JOINT_SECRETARY.value,
            Role.ADMIN.value, 
            Role.ACCOUNTANT.value
        },
        
        # تعلیمی انتظام (عہدیداران + مہتمم تعلیم + ایڈمن)
        'academic_manage': {
            Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, 
            Role.JOINT_SECRETARY.value,
            Role.ADMIN.value, 
            Role.ACADEMIC_HEAD.value
        },
        
        # تعلیمی ریکارڈ دیکھنا (کمیٹی ممبران، اساتذہ وغیرہ سبھی دیکھ سکتے ہیں)
        'academic_view': {
            Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, 
            Role.JOINT_SECRETARY.value,
            Role.COMMITTEE_MEMBER.value,
            Role.ADMIN.value, 
            Role.ACADEMIC_HEAD.value, 
            Role.TEACHER.value, 
            Role.IMAM.value,
            Role.ACCOUNTANT.value
        },

        # اسٹاف کا ریکارڈ دیکھنا (کمیٹی ممبران اور ایڈمنسٹریشن)
        'staff_view': {
            Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value, 
            Role.JOINT_SECRETARY.value,
            Role.COMMITTEE_MEMBER.value,
            Role.ADMIN.value, 
            Role.ACCOUNTANT.value
        }
    }

    def __init__(self, user, institution):
        self.user = user
        self.institution = institution
        
        # بنیادی چیکس (Basic Checks)
        self.is_auth = user and user.is_authenticated
        self.is_superuser = self.is_auth and user.is_superuser
        
        # مالک کا چیک (Owner Check) - بغیر DB query کے اگر institution آبجیکٹ میں user_id موجود ہے
        self.is_owner = self.is_auth and (getattr(institution, 'user_id', None) == user.id)
        
        # اسٹاف رول نکالنا (Staff Role Resolution)
        self.staff_member = None
        self.staff_role = None

        if self.is_auth and not self.is_superuser:
            # نوٹ: View میں 'select_related' استعمال کرنا ضروری ہے ورنہ یہاں DB Query چلے گی
            if hasattr(user, 'staff') and user.staff.institution_id == institution.id:
                self.staff_member = user.staff
                self.staff_role = user.staff.role

    def _has_role_permission(self, permission_key):
        """Helper to check role against the map"""
        allowed_roles = self.PERMISSIONS_MAP.get(permission_key, set())
        return self.staff_role in allowed_roles

    # ---------------------------------------------------
    # 2. Public Boolean Checks (Template یا Logic میں استعمال کے لیے)
    # ---------------------------------------------------

    def can_manage_institution(self):
        """کیا یہ یوزر ادارے کی سیٹنگز تبدیل کر سکتا ہے؟ (Owner/Admin/President/Secretary)"""
        if not self.is_auth: return False
        if self.is_superuser or self.is_owner: return True
        return self.staff_role in {
            Role.ADMIN.value, 
            Role.PRESIDENT.value, 
            Role.VICE_PRESIDENT.value,
            Role.GENERAL_SECRETARY.value,
            Role.JOINT_SECRETARY.value
        }

    def can_view_staff(self):
        """اسٹاف کا ریکارڈ دیکھنا"""
        if self.can_manage_institution(): return True
        return self._has_role_permission('staff_view')

    def can_manage_finance(self):
        """فنانس مینجمنٹ"""
        if self.can_manage_institution(): return True
        return self._has_role_permission('finance_manage')

    def can_manage_academics(self):
        """تعلیمی انتظام (ایڈٹ/ڈیلیٹ)"""
        if self.can_manage_institution(): return True
        return self._has_role_permission('academic_manage')

    def can_view_academics(self):
        """تعلیمی ریکارڈ دیکھنا (ریڈ اونلی)"""
        if self.can_manage_academics(): return True
        return self._has_role_permission('academic_view')

    def is_linked_user(self):
        """کیا یوزر کا ادارے سے کوئی بھی تعلق ہے؟ (Staff, Student, Parent)"""
        if self.can_manage_institution() or self.staff_member:
            return True
        
        # Student Check
        if hasattr(self.user, 'student') and self.user.student.institution_id == self.institution.id:
            return True
            
        # Parent Check
        if hasattr(self.user, 'parent') and self.user.parent.institution_id == self.institution.id:
            return True
            
        return False

    # ---------------------------------------------------
    # 3. Enforcement Methods (Views میں استعمال کے لیے)
    # اگر اجازت نہ ہو تو یہ خود 403 Error دے دیں گے۔
    # ---------------------------------------------------

    def enforce_finance_access(self, student_user=None):
        """
        اگر student_user دیا جائے تو وہ اپنا ڈیٹا دیکھ سکتا ہے۔
        ورنہ صرف Finance Staff کو اجازت ہے۔
        """
        if student_user and student_user == self.user:
            return
        if not self.can_manage_finance():
            raise PermissionDenied("Finance Access Denied: Only Admins or Accountants allowed.")

    def enforce_academic_manage(self):
        if not self.can_manage_academics():
            raise PermissionDenied("Restricted Access: Academic Management only.")
            
    def enforce_academic_view(self):
        if not self.can_view_academics():
            raise PermissionDenied("Restricted Access: Only Academic Staff can view this.")

# ---------------------------------------------------
# 4. Helper Utility for Views (شارٹ کٹ فنکشن)
# ---------------------------------------------------

def get_institution_with_access(slug, request, access_type='view'):
    """
    یہ فنکشن انسٹی ٹیوٹ لاتا ہے اور ساتھ ہی پرمیشن چیک بھی کر لیتا ہے۔
    access_type options: 'view', 'admin', 'finance', 'academic_manage', 'academic_view'
    """
    inst = get_object_or_404(Institution, slug=slug)
    access = InstitutionAccess(request.user, inst)

    # 1. Approval Check (Pending اداروں کو روکنا)
    if not inst.is_approved and not access.is_superuser and not access.is_owner:
        raise PermissionDenied("Institution Pending Approval")

    # 2. Permission Routing (جس قسم کی رسائی مانگی گئی ہے وہ چیک کریں)
    if access_type == 'admin':
        if not access.can_manage_institution():
             raise PermissionDenied("Admin Access Required.")
         
    elif access_type == 'finance':
        access.enforce_finance_access()
         
    elif access_type == 'academic_manage':
        access.enforce_academic_manage()
        
    elif access_type == 'academic_view':
        access.enforce_academic_view()
         
    elif access_type == 'staff_view':
        if not access.can_view_staff():
             raise PermissionDenied("Staff Access Required.")

    # 'view' کے لیے ہم عام طور پر کوئی پابندی نہیں لگاتے سوائے اس کے کہ ادارہ Approved ہو
    
    # access آبجیکٹ کو request کے ساتھ منسلک کر دیں 
    # تاکہ کوئی بھی ٹیمپلیٹ براہ راست `request.access.can_manage_finance()` وغیرہ استعمال کر سکے۔
    request.access = access
    
    return inst, access