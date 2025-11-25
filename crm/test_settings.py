"""
Test settings for running unit tests with SQLite in-memory database.
This provides fast, isolated tests without affecting the development database.
"""

from .settings import *

# ==============================
# Test Database - SQLite in-memory
# ==============================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ==============================
# Speed Optimizations
# ==============================
# Use faster password hasher for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Use in-memory email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable debug for faster tests
DEBUG = False

# Disable logging during tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {},
    "loggers": {},
}

# ==============================
# Static Files - Use simple storage for tests
# ==============================
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# ==============================
# Celery - Run tasks synchronously in tests
# ==============================
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ==============================
# Caching - Use local memory cache for tests
# ==============================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ==============================
# Media - Use temp directory for tests
# ==============================
import tempfile
MEDIA_ROOT = tempfile.mkdtemp()
