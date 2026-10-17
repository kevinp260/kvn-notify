from __future__ import annotations

import smtplib

from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives

from kvn_notify.channels.base import Channel, SendResult
from kvn_notify.conf import notify_settings


def recipient_address(notification) -> str:
    if notification.email:
        return notification.email
    if notification.user_id:
        user = notification.user
        field = get_user_model().get_email_field_name()
        return getattr(user, field, "") or ""
    return ""


class EmailChannel(Channel):
    name = "email"

    def create_deliveries(self, notification) -> list:
        from kvn_notify.models import Delivery

        if not recipient_address(notification):
            return []
        return [Delivery.objects.create(notification=notification, channel=self.name)]

    def send(self, delivery) -> SendResult:
        notification = delivery.notification
        if notification.email_error:
            return SendResult.failed(f"The email could not be rendered: {notification.email_error}")
        address = recipient_address(notification)
        if not address:
            return SendResult.failed("The recipient has no email address.")

        message = EmailMultiAlternatives(
            subject=notification.email_subject or notification.title,
            body=notification.email_text or notification.body,
            from_email=notify_settings.EMAIL["FROM"],
            to=[address],
        )
        if notification.email_html:
            message.attach_alternative(notification.email_html, "text/html")
        try:
            message.send(fail_silently=False)
        except smtplib.SMTPRecipientsRefused as exc:
            return SendResult.failed(f"The mail server refused the address: {exc}")
        except (TimeoutError, smtplib.SMTPException, OSError) as exc:
            return SendResult.retry(f"Could not send the email: {type(exc).__name__}: {exc}")
        return SendResult.sent()
