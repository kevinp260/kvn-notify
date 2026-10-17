"""cancel(), signals, fallback_recipients and the PERMISSION setting."""

import json

import pytest
from django.core import mail
from django.dispatch import receiver
from django.test import Client

from kvn_notify import cancel, notify
from kvn_notify.dispatch import process_due
from kvn_notify.models import Delivery, Notification, PushSubscription
from kvn_notify.signals import delivery_failed, delivery_sent

pytestmark = pytest.mark.django_db(transaction=True)

ALERT = {"name": "Shop", "incident_id": 7}


def add_device(user, name="a"):
    return PushSubscription.objects.create(
        user=user, endpoint=f"https://push.example.com/{user.pk}/{name}", p256dh="k", auth="a"
    )


class PushOutcomes:
    """Fake pywebpush: fail for the endpoints listed in `failing`."""

    def __init__(self):
        self.failing, self.calls = set(), []

    def __call__(self, **kwargs):
        from pywebpush import WebPushException

        endpoint = kwargs["subscription_info"]["endpoint"]
        self.calls.append(endpoint)
        if endpoint in self.failing:
            response = type("R", (), {"status_code": 410, "text": ""})()
            raise WebPushException("gone", response=response)


@pytest.fixture
def pushes(monkeypatch):
    fake = PushOutcomes()
    monkeypatch.setattr("pywebpush.webpush", fake)
    return fake


# --- cancel() -------------------------------------------------------------


def test_cancel_stops_pending_deliveries_and_their_fallback(user, device, pushes, config):
    with config(DISPATCH="worker"):
        notify(user, "monitor.down", {**ALERT, "cause": "x", "monitor_id": 1}, dedupe_key="incident-7-down")
        assert cancel("monitor.down", dedupe_key="incident-7-down") == 1
        process_due()
    assert pushes.calls == [] and mail.outbox == []
    assert Delivery.objects.get().status == "cancelled"


def test_cancel_leaves_sent_deliveries_alone(user, device, pushes):
    notify(user, "monitor.down", {**ALERT, "cause": "x", "monitor_id": 1}, dedupe_key="d1")
    assert cancel("monitor.down", dedupe_key="d1") == 0
    assert Delivery.objects.get().status == "sent"


def test_cancel_by_recipient(user, other_user, pushes, config):
    with config(DISPATCH="worker"):
        notify(
            [user, other_user],
            "leave.approved",
            {"leave_type": "a", "dates": "b", "leave_id": 1},
            channels=["email"],
            dedupe_key="k",
        )
        assert cancel("leave.approved", dedupe_key="k", recipients=user) == 1
        process_due()
    assert [m.to for m in mail.outbox] == [["bob@example.com"]]


# --- signals --------------------------------------------------------------


def test_sent_and_failed_signals(user, device, pushes):
    seen = []

    @receiver(delivery_sent)
    def on_sent(sender, delivery, **kwargs):
        seen.append(("sent", delivery.channel, delivery.status, delivery.notification.data))

    @receiver(delivery_failed)
    def on_failed(sender, delivery, error, **kwargs):
        seen.append(("failed", delivery.channel, delivery.status, error[:10]))

    try:
        notify(user, "alert.group", ALERT, data={"incident_id": 7})
        pushes.failing.add(device.endpoint)
        notify(user, "alert.group", {**ALERT, "incident_id": 8})
    finally:
        delivery_sent.disconnect(on_sent)
        delivery_failed.disconnect(on_failed)
    assert seen[0] == ("sent", "push", "sent", {"incident_id": 7})
    assert seen[1][:3] == ("failed", "push", "failed")


def test_a_broken_receiver_does_not_break_sending(user, device, pushes, caplog):
    def broken(sender, delivery, **kwargs):
        raise RuntimeError("receiver bug")

    delivery_sent.connect(broken)
    try:
        notify(user, "alert.group", ALERT)
    finally:
        delivery_sent.disconnect(broken)
    assert Delivery.objects.get().status == "sent"
    assert "receiver bug" in caplog.text


# --- fallback_recipients --------------------------------------------------


def test_no_fallback_email_when_a_device_takes_the_push(user, pushes):
    add_device(user)
    notify(user, "alert.group", ALERT, fallback_recipients=["ops@example.com"])
    assert len(pushes.calls) == 1 and mail.outbox == []


def test_fallback_email_when_every_device_fails(user, other_user, pushes):
    devices = [add_device(user), add_device(other_user)]
    pushes.failing.update(d.endpoint for d in devices)
    notify(
        [user, other_user],
        "alert.group",
        ALERT,
        data={"incident_id": 7},
        fallback_recipients=["ops@example.com"],
    )
    [email] = mail.outbox
    assert email.to == ["ops@example.com"] and email.subject == "[DOWN] Shop"
    fallback = Notification.objects.get(email="ops@example.com")
    assert fallback.data == {"incident_id": 7}
    assert fallback.deliveries.get().is_fallback is True


def test_no_fallback_when_one_of_several_devices_succeeds(user, other_user, pushes):
    failing = add_device(user)
    add_device(other_user)
    pushes.failing.add(failing.endpoint)
    notify([user, other_user], "alert.group", ALERT, fallback_recipients=["ops@example.com"])
    assert mail.outbox == []


def test_fallback_straight_away_when_nobody_has_a_device(user, pushes):
    notify([], "alert.group", ALERT, fallback_recipients=["ops@example.com", "OPS@example.com"])
    notify(user, "alert.group", {**ALERT, "incident_id": 8}, fallback_recipients=["ops@example.com"])
    assert [m.to for m in mail.outbox] == [["ops@example.com"], ["ops@example.com"]]


def test_fallback_is_sent_once_for_repeated_calls(pushes):
    for _ in range(2):
        notify([], "alert.group", ALERT, dedupe_key="incident-7", fallback_recipients=["ops@example.com"])
    assert len(mail.outbox) == 1


def test_fallback_waits_for_the_worker_and_respects_cancel(user, pushes, config):
    device = add_device(user)
    pushes.failing.add(device.endpoint)
    with config(DISPATCH="worker"):
        notify(user, "alert.group", ALERT, dedupe_key="i7", fallback_recipients=["ops@example.com"])
        process_due()  # push fails -> fallback email queued
        assert mail.outbox == []
        assert cancel("alert.group", dedupe_key="i7") == 1  # the queued fallback email
        process_due()
    assert mail.outbox == []


# --- PERMISSION -----------------------------------------------------------


def deny_everyone(request, user):
    return False


def test_permission_check_can_refuse(user, config):
    client = Client()
    client.force_login(user)
    with config(PERMISSION="tests.test_alerting.deny_everyone"):
        response = client.post("/notify/test/", "{}", content_type="application/json")
    assert response.status_code == 403
    assert "permission" in json.loads(response.content)["error"]
