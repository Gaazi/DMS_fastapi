from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.db import transaction
from django.apps import apps  # Circular Import سے بچنے کے لیے

User = get_user_model()

class UserManager:
    """کامیاب یوزر رجسٹریشن اور پاس ورڈ مینیجمنٹ (Optimized Logic, Same Structure)"""

    @staticmethod
    def generate_username(obj, prefix):
        """Standardized Username: [reg_id] or [Role][ID][RegID]"""
        
        # 1. نیا اور بہتر طریقہ: اگر رجسٹریشن نمبر موجود ہے تو اسی کو چھوٹا کر کے یوزر نیم بنا دو (مثلاً: msj006e001)
        if hasattr(obj, 'reg_id') and obj.reg_id:
            base = obj.reg_id.replace("-", "").replace(" ", "").lower()
            
            counter = 1
            candidate = base
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            
            while UserModel.objects.filter(username=candidate).exists():
                candidate = f"{base}{counter}"
                counter += 1
                
            return candidate

        # 2. پرانا بیک اپ طریقہ (اگر کسی وجہ سے رجسٹریشن نمبر نہیں ہے)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # 1. Role Prefix
        if not prefix: prefix = "user"
        prefix_map = {
            'student': 's',
            'admin': 'a',
            'guardian': 'g',
            'parent': 'g',  # Parent is essentially same as Guardian
            'user': 'u',
        }
        # Get specific code, format it down to 1 character, or use 'e' (for staff, teacher, employee, imam, etc.) as the default for all other roles
        role_code = prefix_map.get(prefix.lower(), 'e')

        # 2. Institution Code
        institution = getattr(obj, "institution", None)
        inst_code = "app"
        
        if institution:
            if hasattr(institution, 'reg_id') and institution.reg_id:
                inst_code = institution.reg_id.replace("-", "").lower()
            else:
                full_slug = getattr(institution, "slug", "inst")
                if full_slug:
                    parts = [word[0] for word in full_slug.split("-") if word]
                    inst_code = "".join(parts)[:3].lower()
        else:
            inst_id = getattr(obj, "institution_id", None) or 1
            inst_code = f"in{inst_id}"
            
        # 3. Unique Identifier (ID Handling Fixed)
        identifier = getattr(obj, 'reg_id', None)
        
        # اگر ID نہیں ہے (نیا آبجیکٹ)، تو عارضی طور پر Random استعمال کریں
        if not identifier:
            identifier = getattr(obj, 'pk', None) or getattr(obj, 'id', None)
        
        if not identifier:
            import random
            identifier = random.randint(1000, 9999) 
        
        # 4. Construct Username
        base = f"{role_code}{identifier}{inst_code}"
        
        # 5. Ensure Uniqueness
        counter = 1
        candidate = base
        while User.objects.filter(username=candidate).exists():
            candidate = f"{base}{counter}"
            counter += 1
        
        return candidate

    @staticmethod
    @transaction.atomic  # اہم تبدیلی: ڈیٹا بیس کو محفوظ رکھنے کے لیے
    def ensure_user(obj, prefix):
        """اگر اکاؤنٹ نہیں ہے تو بنانا (Atomic Transaction کے ساتھ)"""
        
        # اگر پہلے سے یوزر ہے تو واپس جائیں
        if getattr(obj, "user_id", None):
            return None
            
        # اہم فکس: اگر آبجیکٹ نیا ہے اور اس کی ID نہیں ہے، تو پہلے اسے Save کریں
        if not obj.pk:
            obj.save()

        try:
            username = UserManager.generate_username(obj, prefix)
            password = get_random_string(10)
            
            user = User.objects.create(
                username=username,
                email=getattr(obj, "email", "") or "",
                password=make_password(password),
                is_active=True,
            )
            
            obj.user = user
            obj.save(update_fields=["user"])
            
            return password
        except Exception as e:
            # اگر ایرر آیا تو جو یوزر بنا تھا وہ بھی مٹ جائے گا (Rollback)
            raise e

    @staticmethod
    def notify_credentials(request, obj, password):
        """نئے اکاؤنٹ کے کریڈنشلز دکھانا"""
        if password:
            msg = f"نیا یوزر: {obj.user.username} | پاس ورڈ: {password}"
            messages.success(request, msg)
            return msg
        return None

    @staticmethod
    def get_user_institutions(user):
        """یوزر کے تمام ادارے"""
        from django.db.models import Q
        # ماڈل کو متحرک طریقے سے منگوایا گیا تاکہ Circular Import نہ ہو
        Institution = apps.get_model('dms', 'Institution') 
        
        if not user or not user.is_authenticated:
            return Institution.objects.none()

        if user.is_superuser:
            return Institution.objects.all()

        query = Q(user=user)
        if hasattr(user, 'staff') and user.staff.institution_id:
            query |= Q(id=user.staff.institution_id)
        if hasattr(user, 'parent') and user.parent.institution_id:
            query |= Q(id=user.parent.institution_id)
        if hasattr(user, 'student') and user.student.institution_id:
            query |= Q(id=user.student.institution_id)
            
        return Institution.objects.filter(query).distinct()

    @staticmethod
    def pick_primary_institution(user):
        """بنیادی ادارہ چننا"""
        if user.is_superuser: return None

        staff = getattr(user, 'staff', None)
        if staff and staff.institution:
            return staff.institution

        insts = UserManager.get_user_institutions(user)
        return insts.first() if insts.exists() else None

    @staticmethod
    def get_post_login_redirect(user):
        """لاگ ان کے بعد ری ڈائریکٹ"""
        from django.urls import reverse
        
        if user.is_superuser:
            return reverse('institution_overview')
            
        insts = UserManager.get_user_institutions(user)
        count = insts.count()
        
        if count == 0:
            return reverse('no_institution_linked')
            
        if count == 1:
            return reverse('dashboard', kwargs={'institution_slug': insts.first().slug})
            
        # اگر ایک سے زیادہ ادارے ہیں تو ان کو لسٹ دکھانے کے بجائے آپشنلی پہلے والے کے ڈیش بورڈ پر بھیج دیں
        # first_type = insts.first().type
        # return reverse('institution_type_list', kwargs={'institution_type': first_type})
        
        # User will use the account switcher in the header to switch between institutions
        first_inst = insts.first()
        return reverse('dashboard', kwargs={'institution_slug': first_inst.slug})

    @staticmethod
    def handle_signup(request):
        """سائن اپ کا عمل"""
        from django.contrib.auth.forms import UserCreationForm
        
        form = UserCreationForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            user = form.save()
            
            # Specify the backend since we have multiple authentication backends
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            return True, "اکاؤنٹ کامیابی سے بن گیا ہے۔", form
            
        return False, "", form
    @staticmethod
    @transaction.atomic
    def run_smart_auto_cleanup(institution):
        """
        مکمل خودکار روبوٹک صفائی (Fully Automatic Robotic Cleanup)
        - Staff (عملہ): 3 ماہ (90 دن)
        - Student (طلبہ): 6 ماہ (180 دن)
        - Parent (والدین): 12 ماہ (365 دن)
        جو بھی اتنے دن تک لاگ ان نہ کرے اسے خود بخود Inactive کر دے گا
        """
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        import logging
        
        User = get_user_model()
        logger = logging.getLogger(__name__)
        
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        three_months_ago = now - timedelta(days=90)
        six_months_ago = now - timedelta(days=180)
        twelve_months_ago = now - timedelta(days=365)
        
        # 0. صرِف اس ادارے کے صارفین کی لسٹ تیار کریں (Security Sandbox)
        from django.db.models import Q
        from django.apps import apps
        InstitutionModel = apps.get_model('dms', 'Institution')
        # 🚨 گلوبل سیفٹی شیلڈ: سسٹم میں موجود کسی بھی ادارے کے مالک کو کبھی ہاتھ نہ لگاؤ!
        protected_user_ids = list(filter(None, InstitutionModel.objects.values_list('user_id', flat=True)))
        
        # Superusers (ایڈمنز) اور اداروں کے مالکان دونوں مکمل محفوظ ہیں
        base_qs = User.objects.exclude(pk__in=protected_user_ids).exclude(is_superuser=True)
        
        inst_users = base_qs.filter(
            Q(staff__institution=institution) | 
            Q(student__institution=institution) | 
            Q(parent__institution=institution)
        ).distinct()

        # 1. وہ لوگ جو پچھلے 30 دن سے منجدھار میں ہیں (آج تک 1 بار بھی لاگ ان نہیں کیا)
        never_logged_in = inst_users.filter(
            is_active=True,
            last_login__isnull=True,
            date_joined__lte=thirty_days_ago
        )
        
        # 2. اساتذہ/عملہ کی صفائی (3 ماہ)
        inactive_staff = base_qs.filter(
            is_active=True,
            staff__institution=institution,
            last_login__lte=three_months_ago
        )
        
        # 3. طلبہ کی صفائی (6 ماہ)
        inactive_students = base_qs.filter(
            is_active=True,
            student__institution=institution,
            last_login__lte=six_months_ago
        )
        
        # 4. والدین کی صفائی (12 ماہ / 1 سال)
        inactive_parents = base_qs.filter(
            is_active=True,
            parent__institution=institution,
            last_login__lte=twelve_months_ago
        )
        
        # 5. ہارڈ کلین اَپ (Permanent Delete) — 18 ماہ (540 دن)
        # اگر اکاؤنٹ پہلے سے بند (is_active=False) ہے اور 18 ماہ سے استعمال نہیں ہوا، تو اسے جڑ سے مٹا دیں
        eighteen_months_ago = now - timedelta(days=540)
        users_to_permanently_delete = inst_users.filter(
            is_active=False,
            last_login__lte=eighteen_months_ago
        )

        # -- Execution --
        total_suspended = 0
        total_deleted = 0
        
        # ڈیلیٹ کرنے کا عمل (پروفائل ڈیٹا محفوظ رہے گا)
        if users_to_permanently_delete.exists():
            from dms.models import Staff, Student, Parent
            for u in users_to_permanently_delete:
                # 🚨 MULTI-TENANT SAFE DELETION: 
                # Ensure we don't destroy cross-institution accounts!
                has_other_links = (
                    Staff.objects.filter(user=u).exclude(institution=institution).exists() or
                    Student.objects.filter(user=u).exclude(institution=institution).exists() or
                    Parent.objects.filter(user=u).exclude(institution=institution).exists()
                )
                
                if has_other_links:
                    # Safe Disconnect (Unlink only from this institution)
                    Staff.objects.filter(user=u, institution=institution).update(user=None)
                    Student.objects.filter(user=u, institution=institution).update(user=None)
                    Parent.objects.filter(user=u, institution=institution).update(user=None)
                    total_deleted += 1
                else:
                    # Globally delete if no other institution needs this user
                    u.delete()
                    total_deleted += 1
        
        if never_logged_in.exists():
            count = never_logged_in.update(is_active=False)
            total_suspended += count
            
        if inactive_staff.exists():
            count = inactive_staff.update(is_active=False)
            total_suspended += count
            
        if inactive_students.exists():
            count = inactive_students.update(is_active=False)
            total_suspended += count
            
        if inactive_parents.exists():
            count = inactive_parents.update(is_active=False)
            total_suspended += count
            
        if total_suspended > 0 or total_deleted > 0:
            logger.info(f"Auto-Cleanup ran for '{institution.name}'. Suspended {total_suspended}, Deleted {total_deleted}.")
            
        return total_suspended, total_deleted