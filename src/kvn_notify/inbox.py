"""The in-app inbox as plain functions, for apps that write their own endpoints.

kvn-notify's endpoints (KVN_NOTIFY["INBOX"] = True) use these same functions.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone


def inbox_items(user, *, unread_only: bool = False):
    """`user`'s inbox notifications, newest first (a queryset: slice or paginate it)."""
    from kvn_notify.models import Notification

    items = Notification.objects.filter(user=user, in_inbox=True)
    return items.filter(read_at__isnull=True) if unread_only else items


def unread_count(user) -> int:
    return inbox_items(user, unread_only=True).count()


def mark_read(user, notification_id) -> bool:
    """Mark one notification read. False if `user` has no such inbox notification;
    True if it is read now (including when it already was)."""
    items = inbox_items(user).filter(pk=notification_id)
    if items.filter(read_at__isnull=True).update(read_at=timezone.now()):
        return True
    return items.exists()


def mark_all_read(user) -> int:
    """Mark everything read; returns how many changed."""
    return inbox_items(user, unread_only=True).update(read_at=timezone.now())


def serialize(notification) -> dict[str, Any]:
    """The JSON shape the inbox endpoints return for one notification."""
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "data": notification.data,
        "read": notification.read_at is not None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat(),
    }
