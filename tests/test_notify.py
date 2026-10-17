import json
from datetime import timedelta

import pytest
from django.core import mail
from django.db import transaction
from django.utils import timezone

from kvn_notify import notify
from kvn_notify.api import get_preferences, set_preference
from kvn_notify.dispatch import cleanup, process_due
from kvn_notify.exceptions import UnknownNotificationType
from kvn_notify.models import Delivery, Notification

pytestmark = pytest.mark.django_db(transaction=True)

LEAVE = {"leave_type": "Annual leave", "dates": "3-7 Nov", "leave_id": 12}
DOWN = {"name": "Shop", "cause": "Timeout", "monitor_id": 4, "incident_id": 9}


def test_push_and_email_are_sent_with_rendered_fields(user, device, push):
    [notification] = notify(user, "leave.approved", LEAVE)

    assert notification.title == "Your leave request was approved"
    assert notification.body == "Annual leave, 3-7 Nov"
    assert notification.url == "/leaves/12"
    assert set(notification.deliveries.values_list("channel", "status")) == {
        ("email", "sent"),
        ("push", "sent"),
    }

    payload = json.loads(push.calls[0]["data"])
    assert payload["title"] == notification.title
    assert payload["url"] == "/leaves/12"
    assert payload["badge"] == "/static/testapp/badge-96.png"
    assert payload["v"] == 1
    assert push.calls[0]["vapid_claims"] == {"sub": "mailto:admin@example.com"}

    [email] = mail.outbox
    assert email.to == ["alice@example.com"]
    assert email.subject == "Your leave request was approved"
    assert "https://app.example.com/leaves/12" in email.body
    html, mimetype = email.alternatives[0]
    assert mimetype == "text/html"
    assert 'href="https://app.example.com/leaves/12"' in html


def test_nothing_is_sent_when_the_transaction_rolls_back(user, device, push):
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            notify(user, "leave.approved", LEAVE)
            raise RuntimeError("the leave failed to save")

    assert push.calls == []
    assert mail.outbox == []
    assert not Notification.objects.exists()


def test_dedupe_key_stops_a_second_send(user, push):
    first = notify(user, "leave.approved", LEAVE, dedupe_key="leave-12")
    second = notify(user, "leave.approved", LEAVE, dedupe_key="leave-12")
    assert len(first) == 1 and second == []
    assert len(mail.outbox) == 1


def test_user_preference_turns_a_channel_off(user, device, push):
    set_preference(user, "leave.approved", "email", False)
    notify(user, "leave.approved", LEAVE)
    assert mail.outbox == []
    assert len(push.calls) == 1


def test_required_types_ignore_preferences(user, device, push):
    set_preference(user, "monitor.down", "push", False)
    notify(user, "monitor.down", DOWN)
    assert len(push.calls) == 1


def test_get_preferences_lists_types_and_hides_internal_ones(user):
    set_preference(user, "leave.approved", "email", False)
    rows = {row["type"]: row for row in get_preferences(user)}
    assert "kvn_notify.test" not in rows
    assert rows["leave.approved"]["channels"] == {"email": False, "push": True}
    assert rows["monitor.down"]["required"] is True


def test_plain_email_address_gets_the_fallback_when_push_cannot_reach_it(push):
    [notification] = notify("ops@example.com", "monitor.down", DOWN)
    assert push.calls == []
    [email] = mail.outbox
    assert email.to == ["ops@example.com"]
    assert email.subject == "[DOWN] Shop"
    assert notification.deliveries.get().is_fallback is True


def test_user_without_devices_gets_the_fallback_straight_away(user, push):
    notify(user, "monitor.down", DOWN)
    assert [m.to for m in mail.outbox] == [["alice@example.com"]]


def test_dead_device_is_disabled_and_fallback_is_sent(user, device, push):
    push.fail_with = 410
    [notification] = notify(user, "monitor.down", DOWN)

    device.refresh_from_db()
    assert device.active is False
    assert "410" in device.disabled_reason
    push_delivery = notification.deliveries.get(channel="push")
    assert push_delivery.status == "failed"
    assert len(mail.outbox) == 1
    assert notification.deliveries.get(channel="email").is_fallback is True


def test_temporary_error_is_retried_with_growing_waits(user, device, push, config):
    push.fail_with = 503
    with config(MAX_ATTEMPTS=3, RETRY_BASE_SECONDS=60):
        [notification] = notify(user, "group.expense", {"who": "Ana", "amount": "12 EUR"})
        delivery = notification.deliveries.get(channel="push")
        assert delivery.status == "pending"
        assert delivery.attempts == 1
        wait = delivery.next_attempt_at - timezone.now()
        assert timedelta(seconds=50) < wait <= timedelta(seconds=60)

        for expected_wait in (120, None):
            Delivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
            process_due()
            delivery.refresh_from_db()
            if expected_wait:
                assert delivery.status == "pending"
                assert delivery.next_attempt_at - timezone.now() > timedelta(seconds=expected_wait - 10)

    assert delivery.status == "failed"
    assert delivery.attempts == 3
    assert delivery.last_error.startswith("Gave up after 3 attempts")


def test_wrong_vapid_keys_fail_without_retrying(user, device, push):
    push.fail_with = 403
    [notification] = notify(user, "group.expense", {"who": "Ana", "amount": "1"})
    delivery = notification.deliveries.get(channel="push")
    assert delivery.status == "failed"
    assert "VAPID" in delivery.last_error
    device.refresh_from_db()
    assert device.active is True


def test_worker_mode_leaves_deliveries_for_the_worker(user, device, push, config):
    with config(DISPATCH="worker"):
        notify(user, "leave.approved", LEAVE)
        assert push.calls == [] and mail.outbox == []
        assert Delivery.objects.filter(status="pending").count() == 2
        stats = process_due()
    assert stats.sent == 2
    assert len(push.calls) == 1 and len(mail.outbox) == 1


def test_stale_claims_are_released(user, device, push, config):
    with config(DISPATCH="worker"):
        notify(user, "group.expense", {"who": "Ana", "amount": "1"})
        Delivery.objects.filter(channel="push").update(
            status="sending", claimed_at=timezone.now() - timedelta(hours=1)
        )
        process_due()
    assert Delivery.objects.get(channel="push").status == "sent"


def test_inbox_channel_stores_without_sending(user, push):
    [notification] = notify(user, "group.expense", {"who": "Ana", "amount": "12 EUR"})
    assert notification.in_inbox is True
    assert notification.deliveries.get(channel="inbox").status == "sent"


def test_inbox_is_skipped_when_disabled(user, push, config):
    with config(INBOX=False):
        [notification] = notify(user, "group.expense", {"who": "Ana", "amount": "1"})
    assert notification.in_inbox is False
    assert not notification.deliveries.filter(channel="inbox").exists()


def test_custom_email_template_subject_and_escaping(user):
    notify(user, "leave.custom_email", {"leave_type": "Sick <leave>"})
    [email] = mail.outbox
    assert email.subject == "Custom subject for Sick <leave>"
    html = email.alternatives[0][0]
    assert "Hello alice, your Sick &lt;leave&gt; & more." in html
    assert "Custom" in email.body  # plain text built from the title


def test_broken_email_template_fails_the_delivery_not_the_caller(user, monkeypatch):
    def broken(*args, **kwargs):
        raise ValueError("template exploded")

    monkeypatch.setattr("kvn_notify.api.render_email", broken)
    [notification] = notify(user, "leave.approved", LEAVE)
    delivery = notification.deliveries.get(channel="email")
    assert delivery.status == "failed"
    assert "template exploded" in delivery.last_error


def test_unknown_type_and_bad_recipients_raise(user):
    with pytest.raises(UnknownNotificationType):
        notify(user, "no.such.type", {})
    with pytest.raises(ValueError):
        notify("not-an-email", "leave.approved", LEAVE)
    with pytest.raises(TypeError):
        notify(42, "leave.approved", LEAVE)


def test_lists_and_querysets_of_recipients(user, other_user):
    from django.contrib.auth import get_user_model

    created = notify(get_user_model().objects.all(), "leave.approved", LEAVE)
    assert len(created) == 2
    repeated = notify([user, user, "x@example.com", "X@example.com"], "leave.approved", LEAVE)
    assert len(repeated) == 2


def test_cleanup_removes_old_finished_notifications(user, push):
    [old] = notify(user, "leave.approved", LEAVE)
    [inbox_item] = notify(user, "group.expense", {"who": "Ana", "amount": "1"})
    Notification.objects.update(created_at=timezone.now() - timedelta(days=91))
    assert cleanup() == 2
    assert not Notification.objects.filter(pk__in=[old.pk, inbox_item.pk]).exists()


def test_real_encryption_with_generated_keys(user, monkeypatch, config):
    """Runs pywebpush for real (keys, encryption, VAPID header); only the HTTP call is faked."""
    import base64
    import io

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from django.core.management import call_command

    from kvn_notify.models import PushSubscription

    out = io.StringIO()
    call_command("notify_vapid_keys", stdout=out, stderr=io.StringIO())
    keys = dict(line.split("=", 1) for line in out.getvalue().split())

    browser_key = ec.generate_private_key(ec.SECP256R1())
    p256dh = browser_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    PushSubscription.objects.create(
        user=user,
        endpoint="https://fcm.googleapis.com/fcm/send/real",
        p256dh=base64.urlsafe_b64encode(p256dh).decode().rstrip("="),
        auth=base64.urlsafe_b64encode(b"0123456789abcdef").decode().rstrip("="),
    )

    sent = []

    class Response:
        status_code = 201
        text = ""
        headers = {}

    def fake_post(url, data=None, headers=None, timeout=None, **kwargs):
        sent.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return Response()

    monkeypatch.setattr("requests.post", fake_post)
    with config(VAPID_PUBLIC_KEY=keys["VAPID_PUBLIC_KEY"], VAPID_PRIVATE_KEY=keys["VAPID_PRIVATE_KEY"]):
        [notification] = notify(user, "monitor.down", DOWN)

    assert notification.deliveries.get().status == "sent"
    [request] = sent
    headers = {key.lower(): str(value) for key, value in request["headers"].items()}
    assert headers["urgency"] == "high"
    assert headers["ttl"] == "3600"
    assert headers["content-encoding"] == "aes128gcm"
    assert headers["authorization"].startswith("vapid t=")
    assert b"Shop" not in request["data"]  # the payload is encrypted


@pytest.mark.skipif(
    __import__("os").environ.get("KVN_TEST_DB") != "postgres", reason="row locks need PostgreSQL"
)
def test_two_dispatchers_never_take_the_same_delivery(user, device, push, config):
    import threading

    from django.db import connection

    from kvn_notify.dispatch import _claim

    with config(DISPATCH="worker"):
        notify(user, "group.expense", {"who": "Ana", "amount": "1"})
    locked, release = threading.Event(), threading.Event()

    def hold_lock():
        with transaction.atomic():
            list(Delivery.objects.select_for_update().filter(channel="push"))
            locked.set()
            release.wait(5)
        connection.close()

    other = threading.Thread(target=hold_lock)
    other.start()
    try:
        assert locked.wait(5)
        assert _claim(Delivery.objects.all(), 10) == []  # skipped, not waited for
    finally:
        release.set()
        other.join()
    assert len(_claim(Delivery.objects.all(), 10)) == 1
