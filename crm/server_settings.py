import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = False

# ------------------------------
# AWS_STORAGE_BUCKET_NAME = AWS_BUCKET_NAME = os.environ["AWS_BUCKET_NAME"]
# AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
# AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
# S3_DOMAIN = AWS_S3_CUSTOM_DOMAIN = str(AWS_BUCKET_NAME) + ".s3.amazonaws.com"
# AWS_SES_REGION_NAME = os.environ["AWS_SES_REGION_NAME"]
# AWS_SES_REGION_ENDPOINT = os.environ["AWS_SES_REGION_ENDPOINT"]
#
# AWS_S3_OBJECT_PARAMETERS = {
#     "CacheControl": "max-age=86400",
# }
#
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
# DEFAULT_S3_PATH = "media"
#
# MEDIA_ROOT = "/%s/" % DEFAULT_S3_PATH
# MEDIA_URL = "//%s/%s/" % (S3_DOMAIN, DEFAULT_S3_PATH)
# STATIC_URL = "https://%s/" % (S3_DOMAIN)
# ADMIN_MEDIA_PREFIX = STATIC_URL + "admin/"
#
# AWS_IS_GZIPPED = True
# AWS_ENABLED = True
# AWS_S3_SECURE_URLS = True

# ------------------------------
# SMTP Gmail (для продакшн)
# ------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")

# ------------------------------
# CORS
# ------------------------------
CORS_ORIGIN_ALLOW_ALL = True

# ------------------------------
# Сесія
# ------------------------------
SESSION_COOKIE_DOMAIN = ".bottlecrm.com"

# ------------------------------
# Sentry
# ------------------------------
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True,
)

RAVEN_CONFIG = {
    "dsn": os.environ.get("SENTRY_DSN"),
}