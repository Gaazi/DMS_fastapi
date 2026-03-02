from allauth.account.adapter import DefaultAccountAdapter
import uuid
import re

class MyAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to handle user creation via Allauth (Google Sign-In).
    We want to auto-generate usernames from email addresses and bypass the signup form.
    """

    def is_open_for_signup(self, request):
        """Allow signups."""
        return True

    def populate_username(self, request, user):
        """
        Auto-generate a username if not present. called by allauth.
        """
        if not user.username:
            if user.email:
                email_base = user.email.split('@')[0]
                clean_base = re.sub(r'[^a-zA-Z0-9]', '', email_base)
                user.username = f"{clean_base}_{uuid.uuid4().hex[:6]}"
            else:
                user.username = f"user_{uuid.uuid4().hex[:8]}"

    def clean_username(self, username, shallow=False):
        """
        If username is empty (which it might be since we hid the field),
        generate a temporary one to pass validation.
        """
        if not username:
             return f"user_{uuid.uuid4().hex[:8]}"
        return super().clean_username(username, shallow)
