from pathlib import Path
import os
from datetime import timedelta

from corsheaders.defaults import default_headers
from dotenv import load_dotenv
import dj_database_url

# ==============================
# Load environment variables
# ==============================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# ==============================
# Installed applications
# ==============================
INSTALLED_APPS = [
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "cms",
    "wagtail.contrib.settings",
    "modelcluster",
    "taggit",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "phonenumber_field",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "common",
    "accounts",
    "cases",
    "contacts",
    "emails",
    "leads",
    "opportunity",
    "planner",
    "tasks",
    "invoices",
    "events",
    "teams",
]

# ==============================
# Middleware
# ==============================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "crum.CurrentRequestUserMiddleware",
    "common.middleware.get_company.GetProfileAndOrg",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

# ==============================
# Templates
# ==============================
ROOT_URLCONF = "crm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.common.app_name",
                "wagtail.contrib.settings.context_processors.settings",
            ],
        },
    },
]

WSGI_APPLICATION = "crm.wsgi.application"

# ==============================
# Database
# ==============================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:
    DB_NAME = os.environ.get("DBNAME")
    DB_USER = os.environ.get("DBUSER")
    DB_PASSWORD = os.environ.get("DBPASSWORD")
    DB_HOST = os.environ.get("DBHOST", "localhost")
    DB_PORT = os.environ.get("DBPORT", "5432")

    if DB_NAME and DB_USER and DB_PASSWORD:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": DB_NAME,
                "USER": DB_USER,
                "PASSWORD": DB_PASSWORD,
                "HOST": DB_HOST,
                "PORT": DB_PORT,
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

# ==============================
# Password validation
# ==============================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================
# Timezone
# ==============================
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ==============================
# Email — SendGrid SMTP
# ==============================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"   # Always this string
EMAIL_HOST_PASSWORD = os.environ.get("SENDGRID_API_KEY")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@localhost")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@localhost")

# Fix SSL for macOS local dev
if DEBUG and os.environ.get("ENV_TYPE", "dev") == "dev":
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()

AUTH_USER_MODEL = "common.User"

# ==============================
# Static files
# ==============================
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==============================
# Media
# ==============================
ENV_TYPE = os.environ.get("ENV_TYPE", "dev")
print(">>> ENV_TYPE:", ENV_TYPE)

if ENV_TYPE == "dev":
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    MEDIA_URL = "/media/"
elif ENV_TYPE == "prod":
    try:
        from .server_settings import *
    except ImportError:
        pass

# ==============================
# Celery
# ==============================
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ==============================
# Logging
# ==============================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["require_debug_true"],
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ==============================
# Wagtail
# ==============================
APPLICATION_NAME = "bottlecrm"
WAGTAIL_SITE_NAME = "bottlecrm"
WAGTAILADMIN_BASE_URL = "https://bottlecrm.com"

# ==============================
# REST Framework
# ==============================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "common.external_auth.CustomDualAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 10,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BottleCRM API",
    "DESCRIPTION": "Open source CRM application",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ==============================
# CORS
# ==============================
CORS_ALLOW_HEADERS = default_headers + ("org",)
CORS_ORIGIN_ALLOW_ALL = True

CSRF_TRUSTED_ORIGINS = ["https://*.runcode.io", "http://*"]

# ==============================
# Domain
# ==============================
DOMAIN_NAME = os.environ.get("DOMAIN_NAME", "http://localhost:3000")

# ==============================
# JWT
# ==============================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=365),
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
}

JWT_ALGO = "HS256"