"""Settings for the kvn-notify example: Django with templates.

Only the KVN_NOTIFY block and INSTALLED_APPS are specific to kvn-notify;
everything else is a plain Django project.
"""

import os
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
    # --8<-- [start:installed_apps]
    "kvn_notify",
    # --8<-- [end:installed_apps]
    "demo",
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
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# Emails are printed in the terminal of the worker container.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Demo <demo@example.com>"

# A real project reads the keys from environment variables. The example creates
# them on first start so `docker compose up` works with no setup.
VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY = load_or_create_vapid_keys(DATA_DIR / "vapid.env")

# --8<-- [start:kvn_notify]
KVN_NOTIFY = {
    "VAPID_PUBLIC_KEY": VAPID_PUBLIC_KEY,
    "VAPID_PRIVATE_KEY": VAPID_PRIVATE_KEY,
    "VAPID_SUBJECT": "mailto:demo@example.com",
    "BADGE": "demo/badge-96.png",
    "ICON": "demo/icon-192.png",
    "SITE_URL": "http://localhost:8000",
    "DISPATCH": "worker",  # sent by `python manage.py notify_worker`
    "INBOX": True,
    "EMAIL": {"BRAND_NAME": "Demo shop", "PRIMARY_COLOR": "#2563EB"},
}
# --8<-- [end:kvn_notify]
