class KvnNotifyError(Exception):
    """Base class for kvn-notify errors."""


class UnknownNotificationType(KvnNotifyError, LookupError):
    """notify() was called with a type key that was never registered."""


class ImproperlyConfiguredType(KvnNotifyError, ValueError):
    """A NotificationType definition, or the context passed for it, is invalid."""


class UnknownChannel(KvnNotifyError, LookupError):
    """A type names a channel that does not exist."""
