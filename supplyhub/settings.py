"""Django settings for the SupplyHub project."""
from pathlib import Path
import os
import dj_database_url
import cloudinary
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-change-this-before-deployment"
DEBUG = True
ALLOWED_HOSTS = [
    "supplyhub-5bdm.onrender.com",
    "localhost",
    "127.0.0.1",
]

if not DEBUG:
    ALLOWED_HOSTS.extend(
        [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ROOT_URLCONF = "supplyhub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.store_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "supplyhub.wsgi.application"
ASGI_APPLICATION = "supplyhub.asgi.application"


#DATABASE CODE 
#DATABASES = {
 #   "default": {
 #       "ENGINE": "django.db.backends.sqlite3",
 #       "NAME": BASE_DIR / "db.sqlite3",
  #  }
#}



# Use PostgreSQL on Render via DATABASE_URL; keep SQLite as the local fallback
DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///" + str(BASE_DIR / "db.sqlite3")
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

#STATIC_URL = "static/"
#MEDIA_URL = "/media/"
#MEDIA_ROOT = BASE_DIR / "media"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_REDIRECT_URL = "home"

# Development writes sent email to the terminal. Set EMAIL_BACKEND and the
# SMTP environment variables in deployment to deliver real messages.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in {"1", "true", "yes"}
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "SupplyHub <no-reply@supplyhub.local>",
)
SUPPLYHUB_ADMIN_EMAIL = os.getenv("SUPPLYHUB_ADMIN_EMAIL", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
SUPPLYHUB_SELLER_COMMISSION_PERCENT = os.getenv(
    "SUPPLYHUB_SELLER_COMMISSION_PERCENT",
    "5.00",
)
SUPPLYHUB_PAYOUT_HOLD_DAYS = int(os.getenv("SUPPLYHUB_PAYOUT_HOLD_DAYS", "7"))
DELHIVERY_API_TOKEN = os.getenv("DELHIVERY_API_TOKEN", "")
DELHIVERY_API_BASE_URL = os.getenv(
    "DELHIVERY_API_BASE_URL",
    "https://track.delhivery.com",
).rstrip("/")
DELHIVERY_PICKUP_LOCATION = os.getenv("DELHIVERY_PICKUP_LOCATION", "")


# Cloudinary configuration
cloudinary_values = (
    os.getenv("CLOUDINARY_CLOUD_NAME"),
    os.getenv("CLOUDINARY_API_KEY"),
    os.getenv("CLOUDINARY_API_SECRET"),
)
cloudinary_url = os.getenv("CLOUDINARY_URL", "")
has_partial_cloudinary_config = any(cloudinary_values) and not all(cloudinary_values)
if has_partial_cloudinary_config and not cloudinary_url:
    raise ImproperlyConfigured(
        "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET together."
    )
has_cloudinary_config = bool(cloudinary_url) or all(cloudinary_values)
if not DEBUG and not has_cloudinary_config:
    raise ImproperlyConfigured("Configure Cloudinary credentials for production media storage.")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)
STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if has_cloudinary_config
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}