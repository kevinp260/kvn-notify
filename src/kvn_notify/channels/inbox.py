from __future__ import annotations

from django.utils import timezone

from kvn_notify.channels.base import Channel, SendResult
from kvn_notify.conf import notify_settings


class InboxChannel(Channel):
    """The optional in-app list. Nothing travels anywhere: saving it is delivering it."""

    name = "inbox"

    def create_deliveries(self, notification) -> list:
        from kvn_notify.models import Delivery

        if not notify_settings.INBOX or not notification.user_id:
            return []
        if not notification.in_inbox:
            notification.in_inbox = True
            type(notification).objects.filter(pk=notification.pk).update(in_inbox=True)
        now = timezone.now()
        return [
            Delivery.objects.create(
                notification=notification,
                channel=self.name,
                status=Delivery.Status.SENT,
                sent_at=now,
            )
        ]

    def send(self, delivery) -> SendResult:
        return SendResult.sent()
