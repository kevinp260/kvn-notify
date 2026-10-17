"""Push notifications and emails for Django. Declared once, sent with one line, never lost."""

__version__ = "0.1.0"

__all__ = ["NotificationType", "cancel", "notify", "register", "__version__"]


def __getattr__(name):
    # Imported lazily so `import kvn_notify` works before Django's app registry is ready.
    if name in ("notify", "cancel"):
        from kvn_notify import api

        return getattr(api, name)
    if name in ("NotificationType", "register"):
        from kvn_notify import types

        return getattr(types, name)
    raise AttributeError(f"module 'kvn_notify' has no attribute {name!r}")
