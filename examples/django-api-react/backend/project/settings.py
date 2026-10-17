"""Settings for the kvn-notify example: Django as an API, React frontend, JWT login."""

import os
from datetime import timedelta
from pathlib import Path

from project.vapid import load_or_create_vapid_keys

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "example-only-not-secret")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "kvn_notify",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "project.urls"
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
            ]
        },
    }
]
WSGI_APPLICATION = "project.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
STATIC_URL = "/static/"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Demo <demo@example.com>"

# --8<-- [start:drf]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(hours=1)}
# --8<-- [end:drf]

VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY = load_or_create_vapid_keys(DATA_DIR / "vapid.env")

# --8<-- [start:kvn_notify]
KVN_NOTIFY = {
    "VAPID_PUBLIC_KEY": VAPID_PUBLIC_KEY,
    "VAPID_PRIVATE_KEY": VAPID_PRIVATE_KEY,
    "VAPID_SUBJECT": "mailto:demo@example.com",
    # The frontend serves these, so they are URLs rather than static paths.
    "BADGE": "/badge-96.png",
    "ICON": "/icon-192.png",
    "SITE_URL": "http://localhost:5173",
    "DISPATCH": "worker",
    "AUTH": "auto",  # DRF is installed, so the JWT login above is used
    "INBOX": True,
}
# --8<-- [end:kvn_notify]
