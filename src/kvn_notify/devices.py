"""Short, readable device names from a browser's user agent string.

    "Mozilla/5.0 (Linux; Android 10; K) ... Chrome/141.0 Mobile Safari/537.36"
    -> "Chrome on Android"

No library and no guessing beyond the common browsers: anything unrecognised
becomes "Browser on <system>" or just "Browser".
"""

from __future__ import annotations

# Order matters: many browsers also mention "Chrome" or "Safari" in their string.
_BROWSERS = (
    ("EdgA/", "Edge"),
    ("EdgiOS/", "Edge"),
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Opera", "Opera"),
    ("SamsungBrowser/", "Samsung Internet"),
    ("Brave", "Brave"),
    ("Vivaldi/", "Vivaldi"),
    ("YaBrowser/", "Yandex Browser"),
    ("FxiOS/", "Firefox"),
    ("Firefox/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Chromium/", "Chromium"),
    ("Safari/", "Safari"),
)

_SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Macintosh", "macOS"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)


def describe_user_agent(user_agent: str) -> str:
    user_agent = user_agent or ""
    browser = next((name for marker, name in _BROWSERS if marker in user_agent), "")
    system = next((name for marker, name in _SYSTEMS if marker in user_agent), "")
    if browser and system:
        return f"{browser} on {system}"
    if system:
        return f"Browser on {system}"
    return browser or "Browser"


# --- Managing devices -----------------------------------------------------------
# The same functions kvn-notify's own endpoints use, for apps that write their own
# endpoints (or call them from a management command, an admin action, ...).


def register_device(user, subscription: dict, *, user_agent: str = "", device_name: str = ""):
    """Save a browser's push subscription for `user` and return (device, created).

    `subscription` is the browser's PushSubscription.toJSON():
    {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}.
    A device already known moves to `user`, so one phone never gets two people's
    notifications. Raises ValueError for anything malformed or unsafe.
    """
    from kvn_notify.conf import notify_settings
    from kvn_notify.models import PushSubscription, endpoint_hash
    from kvn_notify.security import UnsafeEndpoint, check_push_endpoint

    if not isinstance(subscription, dict):
        raise ValueError("The subscription must be an object.")
    endpoint = subscription.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("'endpoint' is required.")
    if len(endpoint) > 2048:
        raise ValueError("'endpoint' is too long.")
    keys = subscription.get("keys") or {}
    p256dh, auth_secret = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(p256dh, str) and isinstance(auth_secret, str) and p256dh and auth_secret):
        raise ValueError("'keys.p256dh' and 'keys.auth' are required.")
    if len(p256dh) > 255 or len(auth_secret) > 255:
        raise ValueError("Subscription keys are too long.")
    try:
        check_push_endpoint(endpoint, resolve=notify_settings.VALIDATE_PUSH_ENDPOINTS)
    except UnsafeEndpoint as exc:
        raise ValueError(f"Refused push endpoint: {exc}") from None

    user_agent = (user_agent or "")[:512]
    device = PushSubscription.objects.filter(endpoint_hash=endpoint_hash(endpoint)).first()
    created = device is None
    if created:
        device = PushSubscription(endpoint=endpoint)
    device.user = user
    device.p256dh = p256dh
    device.auth = auth_secret
    device.user_agent = user_agent
    # A name the page sends wins; otherwise one is made from the browser's user agent.
    device.device_name = " ".join(str(device_name or "").split())[:120] or describe_user_agent(user_agent)
    device.active = True
    device.disabled_reason = ""
    device.disabled_at = None
    device.save()
    return device, created


def remove_device(user, endpoint: str) -> bool:
    """Forget one of `user`'s devices, e.g. when they turn notifications off or log out."""
    from kvn_notify.models import PushSubscription, endpoint_hash

    deleted, _ = PushSubscription.objects.filter(endpoint_hash=endpoint_hash(endpoint), user=user).delete()
    return bool(deleted)


def remove_devices(user) -> int:
    """Forget all of `user`'s devices: "log out everywhere", a stolen phone, a closed
    account. Their browsers stop receiving pushes; each can subscribe again after
    logging in. Returns how many were removed."""
    from kvn_notify.models import PushSubscription

    deleted, _ = PushSubscription.objects.filter(user=user).delete()
    return deleted


def list_devices(user):
    """`user`'s devices, newest first, for a "your devices" list. Use `device.label` to show them."""
    from kvn_notify.models import PushSubscription

    return PushSubscription.objects.filter(user=user).order_by("-created_at")


def send_test(user) -> int:
    """Push "Notifications are working" to every active device of `user`.
    Returns how many devices it went to (0 means nothing was sent)."""
    from kvn_notify.api import notify
    from kvn_notify.models import PushSubscription

    devices = PushSubscription.objects.filter(user=user, active=True).count()
    if devices:
        notify(user, "kvn_notify.test")
    return devices
