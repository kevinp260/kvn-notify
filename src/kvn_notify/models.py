from __future__ import annotations

import hashlib
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


class PushSubscription(models.Model):
    """One browser or installed app that agreed to receive push notifications."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kvn_push_subscriptions"
    )
    endpoint = models.TextField()
    # Endpoints can be long; a hash keeps the unique index portable across databases.
    endpoint_hash = models.CharField(max_length=64, unique=True, editable=False)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=512, blank=True)
    active = models.BooleanField(default=True)
    disabled_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "push subscription"
        indexes = [models.Index(fields=["user", "active"])]

    def __str__(self) -> str:
        state = "active" if self.active else "inactive"
        return f"Device of {self.user} ({state})"

    def save(self, *args, **kwargs):
        self.endpoint_hash = endpoint_hash(self.endpoint)
        super().save(*args, **kwargs)

    def deactivate(self, reason: str) -> None:
        now = timezone.now()
        PushSubscription.objects.filter(pk=self.pk, active=True).update(
            active=False, disabled_reason=reason[:255], disabled_at=now, updated_at=now
        )
        self.active = False

    def as_subscription_info(self) -> dict:
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}


class Notification(models.Model):
    """One message to one recipient. Its deliveries track each channel and device."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=150, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="kvn_notifications",
    )
    email = models.EmailField(blank=True, help_text="Address for recipients that are not user accounts.")
    # "user:<pk>" or "email:<address>": one key for both kinds of recipient.
    recipient_key = models.CharField(max_length=320, editable=False)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=2048, blank=True)
    tag = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict, blank=True)
    # Email content is rendered when notify() runs, while the context objects exist.
    email_subject = models.CharField(max_length=255, blank=True)
    email_text = models.TextField(blank=True)
    email_html = models.TextField(blank=True)
    email_error = models.TextField(blank=True)
    in_inbox = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    # NULL (not "") so the unique constraint below only applies when a key is given.
    dedupe_key = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient_key", "dedupe_key"],
                condition=Q(dedupe_key__isnull=False),
                name="kvn_notify_unique_dedupe_per_recipient",
            )
        ]
        indexes = [models.Index(fields=["user", "in_inbox", "read_at"])]

    def __str__(self) -> str:
        return f"{self.type} to {self.recipient_label}"

    @property
    def recipient_label(self) -> str:
        return str(self.user) if self.user_id else self.email


class Delivery(models.Model):
    """One attempt route: one channel, and for push one device."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=30)
    subscription = models.ForeignKey(
        PushSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="deliveries"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    is_fallback = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "deliveries"
        ordering = ["created_at"]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]

    def __str__(self) -> str:
        return f"{self.channel} for {self.notification_id} ({self.status})"


class Preference(models.Model):
    """A user's choice to turn one notification type off (or on) for one channel."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kvn_notification_preferences"
    )
    type = models.CharField(max_length=150)
    channel = models.CharField(max_length=30)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "type", "channel"], name="kvn_notify_unique_preference")
        ]

    def __str__(self) -> str:
        state = "on" if self.enabled else "off"
        return f"{self.user}: {self.type} by {self.channel} {state}"
