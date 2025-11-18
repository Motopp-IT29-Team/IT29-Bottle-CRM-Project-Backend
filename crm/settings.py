from pathlib import Path
import os
from datetime import timedelta

from corsheaders.defaults import default_headers
from dotenv import load_dotenv
import dj_database_url

# ==============================
# Load the .env environment file
# ==============================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ==============================
# Basic settings
# ==============================
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
    "django_ses",
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
# Middlewares
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
# Paths and templates
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
# Database - supports both DATABASE_URL and individual DB settings
# ==============================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Production: use DATABASE_URL (Render, Railway, etc.)
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL)
    }
else:
    # Local: try individual DB settings or fallback to SQLite
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
# Language and time zone
# ==============================
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ==============================
# Email settings
# ==============================
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip("'\"")  # Remove quotes

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@localhost")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@localhost")

# Fix SSL certificate issue on macOS for local development
if DEBUG and os.environ.get("ENV_TYPE", "dev") == "dev":
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()

AUTH_USER_MODEL = "common.User"

# ==============================
# Static files
# ==============================
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==============================
# Media files
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
# Celery settings
# ==============================
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ==============================
# Logging settings
# ==============================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[%(server_time)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        },
        "console_debug_false": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "logging.StreamHandler",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "logfile": {
            "class": "logging.FileHandler",
            "filename": "server.log",
        },
    },
    "loggers": {
        "django": {
            "handlers": [
                "console",
                "console_debug_false",
                "logfile",
            ],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==============================
# Wagtail and admin interface settings
# ==============================
APPLICATION_NAME = "bottlecrm"
WAGTAIL_SITE_NAME = "bottlecrm"
WAGTAILADMIN_BASE_URL = "https://bottlecrm.com"
SETTINGS_EXPORT = ["APPLICATION_NAME"]

# ==============================
# REST Framework
# ==============================
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "common.external_auth.CustomDualAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "BottleCRM API",
    "DESCRIPTION": "Open source CRM application",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "PREPROCESSING_HOOKS": ["common.custom_openapi.preprocessing_filter_spec"],
}

SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "crm.urls.info",
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter 'Bearer <token>'",
        },
    },
}

# ==============================
# Security and CORS settings
# ==============================
CORS_ALLOW_HEADERS = default_headers + ("org",)
CORS_ORIGIN_ALLOW_ALL = True
CSRF_TRUSTED_ORIGINS = ["https://*.runcode.io", "http://*"]

SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# ==============================
# Domain settings
# ==============================
DOMAIN_NAME = os.environ.get("DOMAIN_NAME", "http://localhost:3000")
SWAGGER_ROOT_URL = os.environ.get("SWAGGER_ROOT_URL", "http://localhost:8000")

# ==============================
# JWT settings
# ==============================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=365),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

JWT_ALGO = "HS256"