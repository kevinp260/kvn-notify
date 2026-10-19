"""Settings for kvn-notify, read from the KVN_NOTIFY dict in the project's settings.

Every key is optional; the defaults below apply to anything left out.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings as django_settings

DOCS_URL = "https://kevinp260.github.io/kvn-notify"

DEFAULTS: dict[str, Any] = {
    # Web Push. Generate the pair with `python manage.py notify_vapid_keys`.
    "VAPID_PUBLIC_KEY": "",
    "VAPID_PRIVATE_KEY": "",
    "VAPID_SUBJECT": "",  # "mailto:you@example.com" or an https URL
    # Images shown in push notifications. A static path ("icons/badge-96.png")
    # or a full URL. The badge must be a white symbol on a transparent background.
    "ICON": "",
    "BADGE": "",
    "STRICT_ICONS": False,  # turn icon warnings into errors (useful in CI)
    # Public origin of the site, e.g. "https://app.example.com". Needed to turn
    # relative links into absolute ones in emails.
    "SITE_URL": "",
    # How deliveries are sent: "worker" (notify_worker command), "celery", or "inline".
    "DISPATCH": "worker",
    # How the endpoints find the user: "auto", "session", "drf", or a dotted path
    # to a function taking the request and returning a user or None.
    "AUTH": "auto",
    # Optional extra check after login: dotted path to a function(request, user) -> bool,
    # e.g. to require a verified second factor.
    "PERMISSION": None,
    # Headers that carry a login token. Requests with one skip the CSRF check (nothing
    # sends them automatically); every other changing request must pass it.
    # X-Session-Token is django-allauth's header for apps (headless "app" mode).
    "TOKEN_HEADERS": ("Authorization", "X-Session-Token"),
    # Turning this off removes CSRF protection from the endpoints (warning W010).
    "ENFORCE_CSRF": True,
    # Dotted path to a function(user) -> language code or None. Each recipient's copy is
    # then rendered in their language. See the "Languages" guide.
    "LANGUAGE_FOR_USER": None,
    # Remove a user's devices when their password changes, like Django ends their other
    # sessions. They turn notifications on again after logging in.
    "REMOVE_DEVICES_ON_PASSWORD_CHANGE": True,
    # Optional in-app notification list.
    "INBOX": False,
    # Delivery behaviour.
    "MAX_ATTEMPTS": 5,
    "RETRY_BASE_SECONDS": 60,
    "PUSH_TTL": 3600,
    "PUSH_TIMEOUT": 10,
    "VALIDATE_PUSH_ENDPOINTS": True,
    "BATCH_SIZE": 100,
    "WORKER_POLL_SECONDS": 5,
    "STALE_CLAIM_SECONDS": 600,
    # Housekeeping, in days.
    "DELIVERY_RETENTION_DAYS": 90,
    "INBOX_RETENTION_DAYS": 90,
    # Email look and sender. See the "Emails and templates" guide.
    "EMAIL": {
        "FROM": None,  # defaults to DEFAULT_FROM_EMAIL
        "BRAND_NAME": "",
        "LOGO_URL": "",
        "PRIMARY_COLOR": "#2563EB",
        "FOOTER_TEXT": "",
    },
}

VALID_DISPATCH = ("worker", "celery", "inline")


class Settings:
    """Attribute access to KVN_NOTIFY with defaults; re-read on every access so
    `override_settings` in tests works."""

    def _user(self) -> dict[str, Any]:
        return getattr(django_settings, "KVN_NOTIFY", {}) or {}

    def __getattr__(self, name: str) -> Any:
        if name not in DEFAULTS:
            raise AttributeError(f"Unknown kvn-notify setting: {name}")
        value = self._user().get(name, DEFAULTS[name])
        if name == "EMAIL":
            merged = dict(DEFAULTS["EMAIL"])
            merged.update(value or {})
            if not merged["FROM"]:
                merged["FROM"] = getattr(django_settings, "DEFAULT_FROM_EMAIL", None)
            return merged
        return value


notify_settings = Settings()


def docs_link(anchor: str) -> str:
    return f"{DOCS_URL}/troubleshooting/#{anchor}"
