"""The functions apps call: notify(), cancel() and the preference helpers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from kvn_notify import dispatch
from kvn_notify.channels import get_channel
from kvn_notify.emails import render_email
from kvn_notify.models import Delivery, Notification, Preference
from kvn_notify.types import NotificationType, get_type

logger = logging.getLogger("kvn_notify")


def notify(
    recipients: Any,
    type_key: str,
    context: dict[str, Any] | None = None,
    *,
    channels: Iterable[str] | None = None,
    dedupe_key: str | None = None,
    data: dict[str, Any] | None = None,
    fallback_recipients: Any = None,
) -> list[Notification]:
    """Send a registered notification type to one or more recipients.

    recipients: a user, an email address, or a list or queryset of either.
    context: values used to fill the type's title, body, url and email templates.
    channels: overrides the type's channels for this one call (rarely needed).
    dedupe_key: a repeat call with the same key for the same recipient does nothing.
    data: extra JSON-serialisable values stored on the notification and returned by the inbox API.
    fallback_recipients: users or email addresses told, by the type's fallback channel
        (email by default), only if no device of any recipient takes the push. For
        alerts: "push to everyone's phones; if nobody got it, email the on-call inbox".

    Nothing is sent until the surrounding database transaction commits, so a
    change that rolls back never produces a message. Returns the notifications
    created (repeats skipped by dedupe_key are not included).
    """
    ntype = get_type(type_key)
    use_channels = tuple(channels) if channels is not None else tuple(ntype.channels)
    for name in use_channels + ((ntype.fallback,) if ntype.fallback else ()):
        get_channel(name)  # fail fast on a typo, before anything is saved

    group = None
    if fallback_recipients is not None:
        group = _prepare_group(ntype, dict(context or {}), fallback_recipients, dedupe_key, data)

    created: list[Notification] = []
    pending_ids: list[int] = []
    skipped_as_repeat = False
    try:
        for recipient in _normalize_recipients(recipients):
            try:
                with transaction.atomic():
                    result = _create_for_recipient(
                        ntype, recipient, dict(context or {}), use_channels, dedupe_key, data, group
                    )
            except IntegrityError:
                # Another process created the same dedupe_key at the same moment.
                if dedupe_key:
                    skipped_as_repeat = True
                    continue
                raise
            if result is None:
                skipped_as_repeat = True
                continue
            notification, ids = result
            created.append(notification)
            pending_ids.extend(ids)

        if group and not skipped_as_repeat:
            pushed = Delivery.objects.filter(notification__in=created, channel="push").exists()
            if not pushed:
                # Nobody has a device to push to: tell the fallback recipients now.
                pending_ids.extend(create_group_fallback(group))
    finally:
        # Even if a later recipient raises, the ones already saved still get sent
        # (when the caller's transaction commits).
        if pending_ids:
            dispatch.schedule(pending_ids)
    return created


def _create_for_recipient(
    ntype: NotificationType, recipient, context, use_channels, dedupe_key, data, group=None
):
    user = recipient if not isinstance(recipient, str) else None
    email = recipient if isinstance(recipient, str) else ""
    recipient_key = f"user:{user.pk}" if user is not None else f"email:{email.lower()}"

    if (
        dedupe_key
        and Notification.objects.filter(recipient_key=recipient_key, dedupe_key=dedupe_key).exists()
    ):
        return None

    fill = {**context, "recipient": user}
    notification = Notification(
        type=ntype.key,
        user=user,
        email=email,
        recipient_key=recipient_key,
        title=ntype.render("title", fill)[:255],
        body=ntype.render("body", fill),
        url=ntype.render("url", fill)[:2048],
        tag=ntype.render("tag", fill)[:255] if ntype.tag else "",
        data=data or {},
        dedupe_key=dedupe_key,
        group=group["id"] if group else None,
        group_fallback=group or {},
    )

    disabled = _disabled_channels(user, ntype)
    active = [name for name in use_channels if name not in disabled]
    fallback = ntype.fallback if ntype.fallback and ntype.fallback not in disabled else None

    if "email" in active or fallback == "email":
        try:
            subject, text, html = render_email(ntype, notification, fill)
            notification.email_subject, notification.email_text, notification.email_html = subject, text, html
        except Exception as exc:  # a broken template must not break the caller's request
            logger.exception("kvn-notify could not render the email for type %s", ntype.key)
            notification.email_error = f"{type(exc).__name__}: {exc}"[:2000]

    notification.save()

    deliveries: list[Delivery] = []
    for name in active:
        made = get_channel(name).create_deliveries(notification)
        deliveries.extend(made)
        if name == "push" and not made and fallback:
            # No device to push to: use the fallback straight away.
            extra = get_channel(fallback).create_deliveries(notification)
            Delivery.objects.filter(pk__in=[d.pk for d in extra]).update(is_fallback=True)
            deliveries.extend(extra)

    pending = [d.pk for d in deliveries if d.status == Delivery.Status.PENDING]
    return notification, pending


def _prepare_group(ntype: NotificationType, context, fallback_recipients, dedupe_key, data) -> dict:
    """Everything needed to tell the fallback recipients later, rendered now while the
    context objects exist."""
    channel = ntype.fallback or "email"
    get_channel(channel)
    keys = []
    for recipient in _normalize_recipients(fallback_recipients):
        keys.append(f"email:{recipient.lower()}" if isinstance(recipient, str) else f"user:{recipient.pk}")

    fill = {**context, "recipient": None}
    preview = Notification(
        type=ntype.key,
        title=ntype.render("title", fill)[:255],
        body=ntype.render("body", fill),
        url=ntype.render("url", fill)[:2048],
        tag=ntype.render("tag", fill)[:255] if ntype.tag else "",
    )
    email = {"subject": "", "text": "", "html": "", "error": ""}
    if channel == "email":
        try:
            email["subject"], email["text"], email["html"] = render_email(ntype, preview, fill)
        except Exception as exc:
            logger.exception("kvn-notify could not render the fallback email for type %s", ntype.key)
            email["error"] = f"{type(exc).__name__}: {exc}"[:2000]

    group_id = uuid.uuid4()
    return {
        "id": str(group_id),
        "type": ntype.key,
        "channel": channel,
        "recipients": keys,
        "title": preview.title,
        "body": preview.body,
        "url": preview.url,
        "tag": preview.tag,
        "data": data or {},
        "email": email,
        "dedupe_key": f"{dedupe_key}:fallback" if dedupe_key else f"kvn-group:{group_id}",
    }


def create_group_fallback(group: dict) -> list[int]:
    """Create the fallback notifications of a group. Safe to call twice: the second
    call finds them by their dedupe key and creates nothing."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    channel = get_channel(group["channel"])
    pending: list[int] = []
    for key in group["recipients"]:
        kind, _, value = key.partition(":")
        user = user_model.objects.filter(pk=value).first() if kind == "user" else None
        if kind == "user" and user is None:
            continue
        email = group["email"]
        try:
            with transaction.atomic():
                if Notification.objects.filter(recipient_key=key, dedupe_key=group["dedupe_key"]).exists():
                    continue
                notification = Notification.objects.create(
                    type=group["type"],
                    user=user,
                    email=value if kind == "email" else "",
                    recipient_key=key,
                    title=group["title"],
                    body=group["body"],
                    url=group["url"],
                    tag=group["tag"],
                    data=group["data"],
                    email_subject=email["subject"],
                    email_text=email["text"],
                    email_html=email["html"],
                    email_error=email["error"],
                    dedupe_key=group["dedupe_key"],
                    group=group["id"],
                )
                made = channel.create_deliveries(notification)
                Delivery.objects.filter(pk__in=[d.pk for d in made]).update(is_fallback=True)
        except IntegrityError:
            continue  # another dispatcher created it at the same moment
        pending.extend(d.pk for d in made if d.status == Delivery.Status.PENDING)
    return pending


def cancel(type_key: str, *, dedupe_key: str, recipients: Any = None) -> int:
    """Stop notifications that have not been sent yet, e.g. an alert about something
    already fixed. Matches the type and dedupe_key used with notify(), including any
    fallback it queued. Deliveries already sent or being sent are left alone.
    Returns how many deliveries were cancelled."""
    keys = (dedupe_key, f"{dedupe_key}:fallback")
    notifications = Notification.objects.filter(type=type_key, dedupe_key__in=keys)
    if recipients is not None:
        recipient_keys = [
            f"email:{r.lower()}" if isinstance(r, str) else f"user:{r.pk}"
            for r in _normalize_recipients(recipients)
        ]
        notifications = notifications.filter(recipient_key__in=recipient_keys)
    return Delivery.objects.filter(notification__in=notifications, status=Delivery.Status.PENDING).update(
        status=Delivery.Status.CANCELLED, claimed_at=None
    )


def _disabled_channels(user, ntype: NotificationType) -> set[str]:
    if user is None or ntype.required:
        return set()
    return set(
        Preference.objects.filter(user=user, type=ntype.key, enabled=False).values_list("channel", flat=True)
    )


def _normalize_recipients(recipients: Any) -> list:
    user_model = get_user_model()
    if recipients is None:
        return []
    if isinstance(recipients, (str, user_model)) or not isinstance(recipients, Iterable):
        recipients = [recipients]

    result, seen = [], set()
    for item in recipients:
        if item is None:
            continue
        if isinstance(item, str):
            address = item.strip()
            try:
                validate_email(address)
            except ValidationError:
                raise ValueError(f"notify() got {item!r}, which is not a valid email address.") from None
            key = f"email:{address.lower()}"
        elif isinstance(item, user_model):
            if not getattr(item, "is_authenticated", True) or item.pk is None:
                continue
            address = item
            key = f"user:{item.pk}"
        else:
            raise TypeError(
                f"notify() recipients must be users or email addresses, not {type(item).__name__}."
            )
        if key not in seen:
            seen.add(key)
            result.append(address)
    return result


def set_preference(user, type_key: str, channel: str, enabled: bool) -> Preference:
    """Turn one notification type on or off for one channel, for one user."""
    get_type(type_key)
    get_channel(channel)
    preference, _ = Preference.objects.update_or_create(
        user=user, type=type_key, channel=channel, defaults={"enabled": enabled}
    )
    return preference


def get_preferences(user) -> list[dict[str, Any]]:
    """Every registered type with its channels and whether each is on, for a settings screen."""
    from kvn_notify.types import all_types

    stored = {(p.type, p.channel): p.enabled for p in Preference.objects.filter(user=user)}
    rows = []
    for ntype in all_types():
        if ntype.key.startswith("kvn_notify."):
            continue
        rows.append(
            {
                "type": ntype.key,
                "description": ntype.description,
                "required": ntype.required,
                "channels": {
                    name: True if ntype.required else stored.get((ntype.key, name), True)
                    for name in ntype.channels
                },
            }
        )
    return rows
