"""Push notifications and emails for Django. Declared once, sent with one line, never lost."""

__version__ = "0.1.0"

__all__ = ["NotificationType", "notify", "register", "__version__"]


def __getattr__(name):
    # Imported lazily so `import kvn_notify` works before Django's app registry is ready.
    if name == "notify":
        from kvn_notify.api import notify

        return notify
    if name in ("NotificationType", "register"):
        from kvn_notify import types

        return getattr(types, name)
    raise AttributeError(f"module 'kvn_notify' has no attribute {name!r}")
