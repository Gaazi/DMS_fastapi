from sqlmodel import Session, select, or_
from typing import Optional, List, Tuple
import datetime
from jose import JWTError, jwt
from fastapi import Request, Depends, HTTPException
from app.core.config import settings
from app.logic.utils import get_random_string
try:
    import passlib.handlers.bcrypt
    if hasattr(passlib.handlers.bcrypt, "_BcryptWrapBugMixin"):
        passlib.handlers.bcrypt._BcryptWrapBugMixin.detect_wrap_bug = lambda *a, **kw: False
    
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256", "django_pbkdf2_sha256", "md5_crypt", "sha256_crypt"], deprecated="auto")
except ImportError:
    class DummyContext:
        def hash(self, p): return p
        def verify(self, p, h): return p == h
    pwd_context = DummyContext()

# Internal Imports
from app.models import User, Institution, Staff, Student, Parent
from app.core.database import get_session

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    token = request.cookies.get("session_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    user = session.exec(select(User).where(User.username == username)).first()
    return user

class UserLogic:
    """کامیاب یوزر رجسٹریشن اور پاس ورڈ مینیجمنٹ (SQLModel Version)"""

    @staticmethod
    def generate_username(obj, prefix: str, session: Session) -> str:
        """Standardized Username: [reg_id] or [Role][ID][RegID]"""
        
        # 1. اگر رجسٹریشن نمبر موجود ہے
        if hasattr(obj, 'reg_id') and obj.reg_id:
            base = str(obj.reg_id).replace("-", "").replace(" ", "").lower()
            counter = 1
            candidate = base
            
            while session.exec(select(User).where(User.username == candidate)).first():
                candidate = f"{base}{counter}"
                counter += 1
            return candidate

        # 2. پرانا بیک اپ طریقہ
        if not prefix: prefix = "user"
        prefix_map = {
            'student': 's', 'admin': 'a', 'guardian': 'g', 
            'parent': 'g', 'user': 'u'
        }
        role_code = prefix_map.get(prefix.lower(), 'e')

        # Institution Code
        inst_code = "app"
        institution = session.get(Institution, getattr(obj, "inst_id", None))
        if institution:
            if hasattr(institution, 'reg_id') and institution.reg_id:
                inst_code = str(institution.reg_id).replace("-", "").lower()
            else:
                full_slug = getattr(institution, "slug", "inst")
                parts = [word[0] for word in full_slug.split("-") if word]
                inst_code = "".join(parts)[:3].lower()

        identifier = getattr(obj, 'reg_id', None) or getattr(obj, 'id', None) or "rand"
        base = f"{role_code}{identifier}{inst_code}"
        
        counter = 1
        candidate = base
        while session.exec(select(User).where(User.username == candidate)).first():
            candidate = f"{base}{counter}"
            counter += 1
        return candidate

    @staticmethod
    def ensure_user(obj, prefix: str, session: Session) -> Optional[str]:
        """اگر اکاؤنٹ نہیں ہے تو بنانا۔"""
        if getattr(obj, "user_id", None):
            return None

        # Ensure object has ID
        if not obj.id:
            session.add(obj)
            session.flush()

        username = UserLogic.generate_username(obj, prefix, session)
        password = "P" + get_random_string(8) # Simple random password
        
        hashed_password = pwd_context.hash(password)
        
        user = User(
            username=username,
            email=getattr(obj, "email", "") or "",
            password=hashed_password,
            is_active=True,
            date_joined=datetime.datetime.utcnow()
        )
        session.add(user)
        session.flush() # ID حاصل کرنے کے لیے
        
        obj.user_id = user.id
        session.add(obj)
        
        return password

    @staticmethod
    def authenticate(username, password, session: Session) -> Optional[User]:
        """صارف کی تصدیق۔"""
        user = session.exec(select(User).where(User.username == username)).first()
        if user:
            try:
                if pwd_context.verify(password, user.password):
                    return user
            except Exception as e:
                import logging
                logging.getLogger("dms_app").error(f"Password hash error for user {username}: {e}")
                return None
        return None

    @staticmethod
    def get_user_institutions(user: User, session: Session) -> List[Institution]:
        """یوزر کے تمام ملحقہ ادارے حاصل کرنا۔"""
        if not user: return []
        if getattr(user, 'is_superuser', False):
            return session.exec(select(Institution)).all()

        # Query based on ownership, staff link, student link, or parent link
        user_id = user.id
        statement = select(Institution).where(
            or_(
                Institution.user_id == user_id,
                Institution.id.in_(select(Staff.inst_id).where(Staff.user_id == user_id)),
                Institution.id.in_(select(Student.inst_id).where(Student.user_id == user_id)),
                Institution.id.in_(select(Parent.inst_id).where(Parent.user_id == user_id))
            )
        ).distinct()
        
        return list(session.exec(statement))

    @staticmethod
    def get_post_login_redirect(user: User, session: Session = None) -> str:
        """
        لاگ ان کے بعد role کے مطابق صحیح صفحے پر بھیجنا۔
        ترتیب:
        1. Superuser       → /dms-admin
        2. Institution owner (default) → /{slug}/
        3. Staff (role سے) → مختلف صفحات
        4. Student         → student portal
        5. Parent          → parent portal
        6. کچھ نہیں        → /welcome/
        """
        if getattr(user, 'is_superuser', False):
            return "/admin"

        if not session:
            return "/welcome/"

        # 1. Default institution (owner یا linked)
        default_inst = session.exec(
            select(Institution).where(
                Institution.user_id == user.id,
                Institution.is_default == True
            )
        ).first()
        if not default_inst:
            # کوئی بھی approved institution تلاش کریں
            default_inst = session.exec(
                select(Institution).where(
                    Institution.user_id == user.id,
                    Institution.is_approved == True
                )
            ).first()
        if default_inst:
            return f"/{default_inst.slug}/"

        # 2. Staff — role کے مطابق redirect
        staff = session.exec(
            select(Staff).where(Staff.user_id == user.id)
        ).first()
        if staff:
            from app.models.foundation import Institution as Inst
            inst = session.get(Inst, staff.inst_id)
            if inst:
                slug = inst.slug
                role = (staff.role or "").lower()

                # Admin/Management roles → full dashboard
                if role in ('admin', 'president', 'vice_president',
                            'general_secretary', 'joint_secretary', 'committee_member'):
                    return f"/{slug}/"

                # Finance roles → finance page
                elif role in ('accountant',):
                    return f"/{slug}/balance/"

                # Academic roles → attendance page
                elif role in ('teacher', 'imam', 'academic_head'):
                    return f"/{slug}/students/attendance/"

                # Volunteer/other → dashboard
                else:
                    return f"/{slug}/"

        # 3. Student → student self-portal
        student = session.exec(
            select(Student).where(Student.user_id == user.id)
        ).first()
        if student:
            from app.models.foundation import Institution as Inst
            inst = session.get(Inst, student.inst_id)
            if inst:
                return f"/{inst.slug}/students/{student.id}/dashboard/"

        # 4. Parent → parent portal
        parent = session.exec(
            select(Parent).where(Parent.user_id == user.id)
        ).first()
        if parent:
            from app.models.foundation import Institution as Inst
            inst = session.get(Inst, parent.inst_id)
            if inst:
                return f"/{inst.slug}/parent/dashboard/"

        # 5. کوئی link نہیں → welcome
        return "/welcome/"


    @staticmethod
    def handle_signup(data: dict, session: Session) -> Tuple[bool, str, Optional[User]]:
        """نیا اکاؤنٹ بنانے کا عمل۔"""
        username = data.get("username")
        password = data.get("password")
        
        if session.exec(select(User).where(User.username == username)).first():
            return False, "یہ صارف نام پہلے سے موجود ہے۔", None
            
        user = User(
            username=username,
            password=pwd_context.hash(password),
            is_active=True,
            date_joined=datetime.datetime.utcnow()
        )
        session.add(user)
        session.commit()
        return True, "اکاؤنٹ بن گیا ہے۔", user