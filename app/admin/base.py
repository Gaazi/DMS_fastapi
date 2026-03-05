"""
DMS Base Admin View
───────────────────
تمام ModelViews اسے inherit کرتے ہیں۔

Permissions:
  is_superuser  → can_create, can_edit, can_delete = True
  is_staff only → can_create, can_edit, can_delete = False (read-only)
"""
from sqladmin import ModelView
from starlette.requests import Request


class DMSModelView(ModelView):
    """
    Base class for all DMS Admin views.
    Session میں admin_is_superuser چیک کرتا ہے:
      True  → full CRUD
      False → read-only (is_staff user)
    """

    def _is_superuser(self, request: Request) -> bool:
        """Session سے superuser status چیک کریں۔"""
        return request.session.get("admin_is_superuser", False)

    async def scaffold_list(self, request: Request):
        """
        List page پر read-only badge دکھائیں اگر is_staff ہے۔
        """
        return await super().scaffold_list(request)

    # ── Permission Methods ─────────────────────
    def can_create(self, request: Request) -> bool:
        return self._is_superuser(request)

    def can_edit(self, request: Request) -> bool:
        return self._is_superuser(request)

    def can_delete(self, request: Request) -> bool:
        return self._is_superuser(request)

    def can_view_details(self, request: Request) -> bool:
        return True  # سب دیکھ سکتے ہیں
