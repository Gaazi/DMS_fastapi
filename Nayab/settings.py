import os
from pathlib import Path
import environ
env = environ.Env()
# Read .env file if it exists
environ.Env.read_env(os.path.join(Path(__file__).resolve().parent.parent, '.env'))

"""
INDEX / TABLE OF CONTENTS:
--------------------------
Sections:
   - APPS & MIDDLEWARE (Line 20)
   - TEMPLATES (Line 47)
   - DATABASE (Line 66)
   - LOCALES & TIME (Line 82)
   - STATIC & MEDIA (Line 91)
   - SECURITY (Line 100)
"""

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

# ALLOWED_HOSTS - Include your production domain and local test IPs
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['dms.esabaq.com', 'www.dms.esabaq.com', '127.0.0.1', 'localhost'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for allauth

    # Third Party
    'safedelete',
    'simple_history',
    'import_export',
    'django_crontab',
    'widget_tweaks',
    
    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'dms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware', # Allauth middleware
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

SITE_ID = 1

# --- Authentication Backends ---
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'dms.backends.EmailOrUsernameModelBackend',
]

# Allauth Configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = [
    'first_name',
    'last_name',
    'email*',
]
ACCOUNT_EMAIL_VERIFICATION = 'none'

# Social Account Logic
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True
LOGIN_REDIRECT_URL = 'no_institution_linked'
ACCOUNT_LOGOUT_REDIRECT_URL = 'dms_login'

# Custom Adapter
ACCOUNT_ADAPTER = 'dms.adapters.MyAccountAdapter'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

ROOT_URLCONF = 'Nayab.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dms.context_processors.header_payload',
            ],
        },
    },
]

WSGI_APPLICATION = 'Nayab.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': env('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
    }
}

# Add MySQL options only if configured
if 'mysql' in env('DB_ENGINE', default=''):
    DATABASES['default'].update({
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    })
    
# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = False
USE_TZ = True

# Locales for Urdu translations
LOCALE_PATHS = [BASE_DIR / 'locale']

# --- Static Files (CSS, JavaScript, Images) ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise Storage
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000
WHITENOISE_KEEP_ONLY_HASHED_FILES = True

# --- Security Settings (For HTTPS) ---
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = ['https://dms.esabaq.com', 'https://www.dms.esabaq.com']
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGIN_URL = 'dms_login'

# --- Email & Error Reporting ---
ADMINS = [('Administrator', env('ADMIN_EMAIL', default='userid902@gmail.com'))]
SERVER_EMAIL = env('SERVER_EMAIL', default=env('ADMIN_EMAIL', default='userid902@gmail.com'))

# --- PRODUCTION SECURITY GUARANTEES ---
# These activate automatically when DEBUG=False (i.e. on cPanel)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # HSTS prevents downgrade attacks (1 year)
    SECURE_HSTS_SECONDS = 31536000 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# --- Email Error Logging Configuration ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')


# --- Media Files (Uploads) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Logging Configuration (Crucial for cPanel/Production) ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# --- CRON JOBS (100% Fully Automatic Zero-Touch Execution) ---
# Format: ('time_expression', 'module.path.to.logic' OR 'management_command_name', [args], {kwargs})
CRONJOBS = [
    # 0 0 15 * * = Run at 12:00 AM on the 15th of every month!
    ('0 0 15 * *', 'django.core.management.call_command', ['generate_monthly_fees']),
]
