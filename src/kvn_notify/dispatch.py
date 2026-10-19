"""Sending queued deliveries: claiming, retrying, falling back and cleaning up."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from kvn_notify import signals
from kvn_notify.channels import SendResult, get_channel
from kvn_notify.conf import notify_settings
from kvn_notify.types import find_type

logger = logging.getLogger("kvn_notify")


@dataclass
class Stats:
    processed: int = 0
    sent: int = 0
    retried: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, other: Stats) -> None:
        self.processed += other.processed
        self.sent += other.sent
        self.retried += other.retried
        self.failed += other.failed
        self.errors.extend(other.errors)


def _push_handled():
    from kvn_notify.models import Delivery

    # A push still on its way, delivered, or deliberately cancelled: no fallback needed.
    return (Delivery.Status.PENDING, Delivery.Status.SENDING, Delivery.Status.SENT, Delivery.Status.CANCELLED)


def schedule(delivery_ids: list[int]) -> None:
    """Called by notify(): start sending once the caller's transaction commits."""
    mode = notify_settings.DISPATCH
    if mode == "inline":
        transaction.on_commit(lambda: send_now(delivery_ids), robust=True)
    elif mode == "celery":
        transaction.on_commit(lambda: _enqueue_celery(delivery_ids), robust=True)
    # "worker": the notify_worker process picks them up on its next poll.


def _enqueue_celery(delivery_ids: list[int]) -> None:
    from kvn_notify.tasks import send_deliveries

    try:
        send_deliveries.delay(delivery_ids)
    except Exception:
        # The broker is down. The rows stay pending and the periodic task sends them later.
        logger.warning(
            "kvn-notify could not reach the Celery broker; %d deliveries wait for the next sweep",
            len(delivery_ids),
        )


def send_now(delivery_ids: list[int]) -> Stats:
    """Send specific deliveries right away (inline mode and Celery tasks)."""
    from kvn_notify.models import Delivery

    claimed = _claim(Delivery.objects.filter(pk__in=delivery_ids), len(delivery_ids))
    return _process(claimed)


def process_due(limit: int | None = None) -> Stats:
    """Send every delivery that is due, up to `limit`. Used by the worker and periodic tasks."""
    from kvn_notify.models import Delivery

    _release_stale_claims()
    limit = limit or notify_settings.BATCH_SIZE
    claimed = _claim(Delivery.objects.all(), limit)
    return _process(claimed)


def _claim(queryset, limit: int) -> list[int]:
    """Mark due deliveries as being sent, so no other dispatcher takes them.

    On PostgreSQL and MySQL the row lock with SKIP LOCKED lets several dispatchers
    run side by side. SQLite has no row locks; the status check below still stops
    a delivery being taken twice, but run a single dispatcher there.
    """
    from kvn_notify.models import Delivery

    now = timezone.now()
    with transaction.atomic():
        ids = list(
            queryset.select_for_update(skip_locked=True)
            .filter(status=Delivery.Status.PENDING, next_attempt_at__lte=now)
            .order_by("next_attempt_at", "pk")
            .values_list("pk", flat=True)[:limit]
        )
        claimed = [
            pk
            for pk in ids
            if Delivery.objects.filter(pk=pk, status=Delivery.Status.PENDING).update(
                status=Delivery.Status.SENDING, claimed_at=now
            )
        ]
    return claimed


def _release_stale_claims() -> None:
    """Deliveries left 'sending' by a dispatcher that crashed go back in the queue."""
    from kvn_notify.models import Delivery

    cutoff = timezone.now() - timedelta(seconds=notify_settings.STALE_CLAIM_SECONDS)
    Delivery.objects.filter(status=Delivery.Status.SENDING, claimed_at__lt=cutoff).update(
        status=Delivery.Status.PENDING, claimed_at=None
    )


def _process(delivery_ids: list[int]) -> Stats:
    from kvn_notify.models import Delivery

    stats = Stats()
    deliveries = Delivery.objects.filter(pk__in=delivery_ids).select_related(
        "notification", "notification__user", "subscription"
    )
    for delivery in deliveries:
        stats.processed += 1
        try:
            result = get_channel(delivery.channel).send(delivery)
        except Exception as exc:  # a channel must not raise, but one bad row cannot stop the batch
            logger.exception("kvn-notify channel %s raised for delivery %s", delivery.channel, delivery.pk)
            result = SendResult.retry(f"{type(exc).__name__}: {exc}")
        outcome = _record(delivery, result)
        if outcome == "sent":
            stats.sent += 1
        elif outcome == "retry":
            stats.retried += 1
        else:
            stats.failed += 1
            stats.errors.append(result.error)
            if delivery.channel == "push" and not delivery.is_fallback:
                _maybe_fall_back(delivery.notification_id)
                if delivery.notification.group:
                    _maybe_group_fallback(delivery.notification)
    return stats


def _record(delivery, result: SendResult) -> str:
    from kvn_notify.models import Delivery

    now = timezone.now()
    attempts = delivery.attempts + 1
    fields = {"attempts": attempts, "claimed_at": None, "updated_at": now}

    if result.status == "sent":
        Delivery.objects.filter(pk=delivery.pk).update(
            status=Delivery.Status.SENT, sent_at=now, last_error="", **fields
        )
        delivery.status, delivery.sent_at, delivery.attempts = Delivery.Status.SENT, now, attempts
        _send_signal(signals.delivery_sent, delivery)
        return "sent"

    if result.status == "retry" and attempts < notify_settings.MAX_ATTEMPTS:
        wait = notify_settings.RETRY_BASE_SECONDS * (2 ** (attempts - 1))
        Delivery.objects.filter(pk=delivery.pk).update(
            status=Delivery.Status.PENDING,
            next_attempt_at=now + timedelta(seconds=wait),
            last_error=result.error[:2000],
            **fields,
        )
        return "retry"

    error = result.error
    if result.status == "retry":
        error = f"Gave up after {attempts} attempts. Last error: {error}"
    Delivery.objects.filter(pk=delivery.pk).update(
        status=Delivery.Status.FAILED, last_error=error[:2000], **fields
    )
    logger.warning("kvn-notify delivery %s (%s) failed: %s", delivery.pk, delivery.channel, error)
    delivery.status, delivery.last_error, delivery.attempts = Delivery.Status.FAILED, error, attempts
    _send_signal(signals.delivery_failed, delivery, error=error)
    return "failed"


def _send_signal(signal, delivery, **kwargs) -> None:
    from kvn_notify.models import Delivery

    for receiver, response in signal.send_robust(sender=Delivery, delivery=delivery, **kwargs):
        if isinstance(response, Exception):
            logger.error(
                "kvn-notify signal receiver %r failed for delivery %s",
                receiver,
                delivery.pk,
                exc_info=(type(response), response, response.__traceback__),
            )


def _maybe_fall_back(notification_id) -> None:
    """When no device took a push, send the type's fallback channel instead (once)."""
    from kvn_notify.api import _disabled_channels
    from kvn_notify.models import Delivery, Notification

    with transaction.atomic():
        # No select_related here: PostgreSQL cannot lock rows across the nullable user join.
        notification = Notification.objects.select_for_update().get(pk=notification_id)
        ntype = find_type(notification.type)
        if not ntype or not ntype.fallback:
            return
        if notification.deliveries.filter(channel="push", status__in=_push_handled()).exists():
            return
        if notification.deliveries.filter(is_fallback=True).exists():
            return
        if ntype.fallback in _disabled_channels(notification.user, ntype):
            return
        made = get_channel(ntype.fallback).create_deliveries(notification)
        ids = [d.pk for d in made]
        Delivery.objects.filter(pk__in=ids).update(is_fallback=True)
        pending = [d.pk for d in made if d.status == Delivery.Status.PENDING]
    _send_follow_ups(pending)


def _maybe_group_fallback(notification) -> None:
    """When no device of anyone in a notify() call took the push, tell its fallback
    recipients (once)."""
    from kvn_notify.api import create_group_fallback
    from kvn_notify.models import Delivery

    if not notification.group_fallback:
        return
    in_group = Delivery.objects.filter(notification__group=notification.group, channel="push")
    if in_group.filter(status__in=_push_handled()).exists():
        return
    _send_follow_ups(create_group_fallback(notification.group_fallback))


def _send_follow_ups(pending: list[int]) -> None:
    if not pending:
        return
    if notify_settings.DISPATCH == "inline":
        send_now(pending)
    else:
        schedule(pending)


def cleanup() -> int:
    """Delete old notifications and long-dead devices. Returns how many notifications
    were removed."""
    from kvn_notify.models import Delivery, Notification, PushSubscription

    now = timezone.now()
    busy = (Delivery.Status.PENDING, Delivery.Status.SENDING)
    removed = 0
    groups = (
        (False, notify_settings.DELIVERY_RETENTION_DAYS),
        (True, notify_settings.INBOX_RETENTION_DAYS),
    )
    for in_inbox, days in groups:
        if not days:
            continue
        old = Notification.objects.filter(
            in_inbox=in_inbox, created_at__lt=now - timedelta(days=days)
        ).exclude(deliveries__status__in=busy)
        removed += old.delete()[1].get("kvn_notify.Notification", 0)

    days = notify_settings.INACTIVE_DEVICE_RETENTION_DAYS
    if days:
        PushSubscription.objects.filter(
            active=False, disabled_at__lt=now - timedelta(days=days)
        ).delete()
    return removed
