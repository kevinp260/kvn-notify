from __future__ import annotations

import json
import logging

from django.utils import timezone

from kvn_notify.channels.base import Channel, SendResult
from kvn_notify.conf import notify_settings
from kvn_notify.icons import image_url
from kvn_notify.security import UnsafeEndpoint, check_push_endpoint
from kvn_notify.types import find_type

logger = logging.getLogger("kvn_notify")

PAYLOAD_VERSION = 1
MAX_TITLE = 200
MAX_BODY = 1000


def build_payload(notification) -> dict:
    """The message the service worker receives. Documented in docs/payload.md;
    bump PAYLOAD_VERSION on any incompatible change."""
    return {
        "v": PAYLOAD_VERSION,
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title[:MAX_TITLE],
        "body": notification.body[:MAX_BODY],
        "url": notification.url or "/",
        "tag": notification.tag or str(notification.id),
        "icon": image_url(notify_settings.ICON),
        "badge": image_url(notify_settings.BADGE),
        "inbox": notification.in_inbox,
    }


class WebPushChannel(Channel):
    name = "push"

    def create_deliveries(self, notification) -> list:
        from kvn_notify.models import Delivery, PushSubscription

        if not notification.user_id:
            return []
        subscriptions = PushSubscription.objects.filter(user_id=notification.user_id, active=True)
        return [
            Delivery.objects.create(notification=notification, channel=self.name, subscription=sub)
            for sub in subscriptions
        ]

    def send(self, delivery) -> SendResult:
        from pywebpush import WebPushException, webpush
        from requests import RequestException

        subscription = delivery.subscription
        if subscription is None:
            return SendResult.failed("The device was removed.")
        if not subscription.active:
            return SendResult.failed(f"The device is inactive: {subscription.disabled_reason or 'disabled'}.")

        private_key = notify_settings.VAPID_PRIVATE_KEY
        subject = notify_settings.VAPID_SUBJECT
        if not (private_key and subject):
            return SendResult.retry(
                "VAPID_PRIVATE_KEY or VAPID_SUBJECT is not set in KVN_NOTIFY; push cannot be sent."
            )

        if notify_settings.VALIDATE_PUSH_ENDPOINTS:
            try:
                # Checked again right before sending, so a stored hostname cannot be
                # re-pointed at an internal address after it was accepted.
                check_push_endpoint(subscription.endpoint)
            except UnsafeEndpoint as exc:
                subscription.deactivate(f"Unsafe endpoint: {exc}")
                return SendResult.failed(f"Refused unsafe push endpoint: {exc}")

        notification = delivery.notification
        ntype = find_type(notification.type)
        ttl = ntype.ttl if ntype and ntype.ttl is not None else notify_settings.PUSH_TTL
        urgency = ntype.urgency if ntype else "normal"

        try:
            webpush(
                subscription_info=subscription.as_subscription_info(),
                data=json.dumps(build_payload(notification), separators=(",", ":")),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=ttl,
                timeout=notify_settings.PUSH_TIMEOUT,
                headers={"Urgency": urgency},
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            return self._result_for_status(subscription, status, exc)
        except RequestException as exc:
            return SendResult.retry(f"Could not reach the push service: {type(exc).__name__}: {exc}")
        except Exception as exc:  # pywebpush can raise on malformed keys
            logger.exception("Unexpected error sending push for delivery %s", delivery.pk)
            return SendResult.failed(f"Unexpected error: {type(exc).__name__}: {exc}")

        type(subscription).objects.filter(pk=subscription.pk).update(last_success_at=timezone.now())
        return SendResult.sent()

    @staticmethod
    def _result_for_status(subscription, status, exc) -> SendResult:
        detail = f"Push service answered {status or 'with an error'}: {exc}"
        if status in (404, 410):
            # The browser unsubscribed or the app was uninstalled; the endpoint is dead.
            subscription.deactivate(f"Push service answered {status}")
            return SendResult.failed(detail)
        if status == 413:
            return SendResult.failed(detail + " (message too large)")
        if status in (400, 401, 403):
            # Usually wrong VAPID keys: the subscription was made with a different key pair.
            return SendResult.failed(detail + " (check the VAPID keys)")
        return SendResult.retry(detail)
