"""
Admin Authentication Backend
─────────────────────────────
Access levels:
  is_superuser=True → full access (create, edit, delete)
  is_staff=True     → read-only access (صرف دیکھ سکتا ہے)
  باقی              → /login/ پر redirect

App کا JWT cookie (session_token) استعمال کرتا ہے۔
"""
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse


class AdminAuth(AuthenticationBackend):
    """
    SQLAdmin Authentication Backend۔
    - is_superuser → full CRUD access
    - is_staff     → read-only (session میں محفوظ)
    - باقی سب     → /login/ پر redirect
    """

    async def login(self, request: Request) -> bool:
        """
        SQLAdmin کا اپنا login form استعمال نہیں کرتے۔
        Main app login (/login/) سے ہی session ملتا ہے۔
        """
        return False

    async def logout(self, request: Request) -> bool:
        """Logout — cookie main app سے clear ہوتی ہے۔"""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        ہر request پر JWT cookie check کرتا ہے۔
        - is_superuser → True (full access)
        - is_staff     → True (read-only, session میں flag)
        - نہ کوئی     → Redirect
        """
        from jose import JWTError, jwt
        from sqlmodel import Session, select
        from app.core.database import engine
        from app.models import User
        from app.core.config import settings

        # 1. Cookie موجود ہے؟
        token = request.cookies.get("session_token")
        if not token:
            return RedirectResponse(
                url="/login/?next=/admin/",
                status_code=302
            )

        # 2. Token valid ہے؟
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            username = payload.get("sub")
            if not username:
                return RedirectResponse(url="/login/", status_code=302)
        except JWTError:
            return RedirectResponse(url="/login/", status_code=302)

        # 3. is_superuser یا is_staff چیک کرو
        with Session(engine) as db:
            user = db.exec(
                select(User).where(User.username == username)
            ).first()

            if not user:
                return RedirectResponse(url="/login/", status_code=302)

            is_super = getattr(user, "is_superuser", False)
            is_staff = getattr(user, "is_staff", False)

            # نہ superuser نہ staff — access نہیں
            if not is_super and not is_staff:
                return RedirectResponse(
                    url="/?error=admin_access_denied",
                    status_code=302
                )

            # Session میں role محفوظ کریں (ModelViews استعمال کریں گے)
            request.session["admin_username"] = username
            request.session["admin_is_superuser"] = is_super

        return True
