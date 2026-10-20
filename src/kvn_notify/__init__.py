"""Push notifications and emails for Django. Declared once, sent with one line, never lost."""

__version__ = "1.0.0"

__all__ = [
    "NotificationType",
    "acancel",
    "anotify",
    "cancel",
    "export_user_data",
    "get_preferences",
    "list_devices",
    "notify",
    "register",
    "register_device",
    "remove_device",
    "remove_devices",
    "send_test",
    "set_preference",
    "__version__",
]

_LAZY = {
    "notify": "api",
    "anotify": "api",
    "cancel": "api",
    "acancel": "api",
    "get_preferences": "api",
    "set_preference": "api",
    "export_user_data": "api",
    "NotificationType": "types",
    "register": "types",
    "register_device": "devices",
    "remove_device": "devices",
    "remove_devices": "devices",
    "list_devices": "devices",
    "send_test": "devices",
}


def __getattr__(name):
    # Imported lazily so `import kvn_notify` works before Django's app registry is ready.
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(f"kvn_notify.{_LAZY[name]}"), name)
    raise AttributeError(f"module 'kvn_notify' has no attribute {name!r}")
