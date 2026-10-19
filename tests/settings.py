import os

SECRET_KEY = "kvn-notify-tests-only-not-a-real-secret-key"
DEBUG = False
USE_TZ = True
ROOT_URLCONF = "tests.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "django.contrib.messages",
    "rest_framework",
    "rest_framework.authtoken",
    "kvn_notify",
    "tests.testapp",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

if os.environ.get("KVN_TEST_DB") == "postgres":  # used in CI
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "kvn_notify"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

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

STATIC_URL = "/static/"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "app@example.com"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

KVN_NOTIFY = {
    "VAPID_PUBLIC_KEY": "BPublicKeyForTests",
    "VAPID_PRIVATE_KEY": "private-key-for-tests",
    "VAPID_SUBJECT": "mailto:admin@example.com",
    "BADGE": "testapp/badge-96.png",
    "ICON": "testapp/icon-192.png",
    "SITE_URL": "https://app.example.com",
    "DISPATCH": "inline",
    "AUTH": "session",
    "VALIDATE_PUSH_ENDPOINTS": False,
    "INBOX": True,
}

# dj-rest-auth's JWT-in-a-cookie login, used by tests/test_login_setups.py. Its own CSRF
# check (JWT_AUTH_COOKIE_USE_CSRF) is left at the default, off, on purpose.
REST_AUTH = {"USE_JWT": True, "JWT_AUTH_COOKIE": "app-auth"}
