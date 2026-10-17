"""Notification types: each kind of message an app sends, declared once.

    register(NotificationType(
        key="leave.approved",
        channels=["email", "push"],
        title="Your leave request was approved",
        body="{leave.leave_type.name}, {dates}",
        url="/leaves/{leave.id}",
    ))

Text fields are Python format strings filled from the context passed to notify(),
or callables that take the context dict and return a string.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from kvn_notify.exceptions import ImproperlyConfiguredType, UnknownNotificationType

TextValue = str | Callable[[dict[str, Any]], str]

URGENCIES = ("very-low", "low", "normal", "high")


@dataclass(frozen=True)
class NotificationType:
    key: str
    title: TextValue
    body: TextValue = ""
    url: TextValue = ""
    channels: Sequence[str] = field(default=("push",))
    # Channel to use when a push reaches no device: no devices, or every device failed.
    fallback: str | None = None
    # Required types ignore user preferences (security and outage alerts).
    required: bool = False
    # "app/email/thing" -> app/email/thing.html, .txt and _subject.txt (all optional but .html).
    email_template: str | None = None
    email_subject: TextValue | None = None
    # Notifications with the same tag replace each other on the device.
    tag: TextValue | None = None
    ttl: int | None = None
    urgency: str = "normal"
    # Shown to users on a settings screen, if the app builds one.
    description: str = ""

    def __post_init__(self):
        if not self.key or not isinstance(self.key, str):
            raise ImproperlyConfiguredType("A notification type needs a non-empty string key.")
        channels = tuple(self.channels)
        if not channels:
            raise ImproperlyConfiguredType(f"Notification type {self.key!r} has no channels.")
        if len(set(channels)) != len(channels):
            raise ImproperlyConfiguredType(f"Notification type {self.key!r} lists a channel twice.")
        object.__setattr__(self, "channels", channels)
        if self.fallback and self.fallback in channels:
            raise ImproperlyConfiguredType(
                f"Notification type {self.key!r}: fallback {self.fallback!r} is already one of its "
                "channels, so it would be sent twice."
            )
        if self.urgency not in URGENCIES:
            raise ImproperlyConfiguredType(
                f"Notification type {self.key!r}: urgency must be one of {', '.join(URGENCIES)}."
            )

    def render(self, attribute: str, context: dict[str, Any]) -> str:
        value = getattr(self, attribute)
        if value is None:
            return ""
        if callable(value):
            return str(value(context))
        try:
            return value.format(**context)
        except (KeyError, AttributeError, IndexError) as exc:
            raise ImproperlyConfiguredType(
                f"Notification type {self.key!r}: could not fill {attribute} {value!r} from the "
                f"context passed to notify(): {exc!r}. Pass the missing value in the context."
            ) from exc


_registry: dict[str, NotificationType] = {}


def register(notification_type: NotificationType) -> NotificationType:
    """Register a type so notify() can send it. Returns the type, so it can be kept in a variable."""
    existing = _registry.get(notification_type.key)
    if existing is not None and existing != notification_type:
        raise ImproperlyConfiguredType(
            f"Notification type {notification_type.key!r} is registered twice with different settings."
        )
    _registry[notification_type.key] = notification_type
    return notification_type


def unregister(key: str) -> None:
    _registry.pop(key, None)


def get_type(key: str) -> NotificationType:
    try:
        return _registry[key]
    except KeyError:
        raise UnknownNotificationType(
            f"No notification type {key!r} is registered. Declare it with register(NotificationType(...)) "
            "in a notification_types.py module of one of your apps."
        ) from None


def find_type(key: str) -> NotificationType | None:
    return _registry.get(key)


def all_types() -> list[NotificationType]:
    return sorted(_registry.values(), key=lambda t: t.key)
