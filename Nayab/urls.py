# Nayab/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from dms import views as dms_views
from django.conf import settings
from django.conf.urls.static import static

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Paths:
   - /login/, /logout/
   - /password_reset/
   - /admin/
   - / (Root) -> dms.urls
"""


urlpatterns = [

    # ======== Authentication ========
    # Use the custom login view so users land on the right dashboard
    path('login/', dms_views.dms_login, name='dms_login'),

    # Built-in Logout View (no file required)
    path('logout/', dms_views.dms_logout, name='logout'),

    # Password Reset URLs
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # ======== App URLs ========
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')), # Allauth URLs
    path('', include('dms.urls')),   # Delegate application URLs to the dms app
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
