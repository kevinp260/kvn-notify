"""The functions apps call directly: devices, inbox, async, export, language,
and devices removed on a password change."""

import asyncio

import pytest
from django.contrib.auth import get_user_model

from kvn_notify import (
    anotify,
    export_user_data,
    inbox,
    list_devices,
    notify,
    register_device,
    remove_device,
    remove_devices,
    send_test,
    set_preference,
)
from kvn_notify.models import Notification, PushSubscription

pytestmark = pytest.mark.django_db(transaction=True)

SUBSCRIPTION = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/phone",
    "keys": {"p256dh": "BNcRdreALRFX", "auth": "tBHItJI5svbpez7KI4CCXg"},
}
ANDROID = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Mobile Safari/537.36"
)


# Devices ------------------------------------------------------------------------


def test_register_list_and_remove_a_device(user, other_user):
    device, created = register_device(user, SUBSCRIPTION, user_agent=ANDROID)
    assert created and device.user == user and device.label == "Chrome on Android"
    assert list(list_devices(user)) == [device]

    # The same browser for another person moves to them.
    moved, created = register_device(other_user, SUBSCRIPTION, device_name="  Bob's   phone ")
    assert not created and moved.pk == device.pk and moved.user == other_user
    assert moved.label == "Bob's phone"

    assert not remove_device(user, SUBSCRIPTION["endpoint"])  # not alice's any more
    assert remove_device(other_user, SUBSCRIPTION["endpoint"])
    assert not PushSubscription.objects.exists()


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"endpoint": "https://push.example.com/x"},
        {"endpoint": "https://push.example.com/x", "keys": {"p256dh": "k"}},
        {"endpoint": "http://push.example.com/x", "keys": {"p256dh": "k", "auth": "a"}},
    ],
)
def test_register_device_refuses_bad_subscriptions(user, bad):
    with pytest.raises(ValueError):
        register_device(user, bad)


def test_remove_devices_and_send_test(user, push):
    assert send_test(user) == 0
    register_device(user, SUBSCRIPTION)
    register_device(user, {**SUBSCRIPTION, "endpoint": "https://fcm.googleapis.com/fcm/send/laptop"})
    assert send_test(user) == 2
    assert remove_devices(user) == 2
    assert not list_devices(user).exists()


# Inbox ----------------------------------------------------------------------------


def test_inbox_functions(user, other_user, push):
    first, second = (notify(user, "group.expense", {"who": "Ana", "amount": n})[0] for n in (1, 2))
    notify(other_user, "group.expense", {"who": "Ana", "amount": 3})
    assert inbox.unread_count(user) == 2
    assert list(inbox.inbox_items(user)) == [second, first]
    assert inbox.mark_read(user, first.pk) is True
    assert inbox.mark_read(user, first.pk) is True  # already read: still fine
    assert inbox.mark_read(other_user, first.pk) is False  # not theirs
    assert list(inbox.inbox_items(user, unread_only=True)) == [second]
    assert inbox.mark_all_read(user) == 1
    assert inbox.unread_count(user) == 0
    first.refresh_from_db()
    assert inbox.serialize(first)["read"] is True


# Async ------------------------------------------------------------------------------


def test_anotify_from_async_code(user, push):
    async def view():
        return await anotify(user, "group.expense", {"who": "Ana", "amount": 5})

    created = asyncio.run(view())
    assert len(created) == 1
    assert Notification.objects.get().title == "Ana added 5"


# Export -------------------------------------------------------------------------------


def test_export_user_data_has_everything_but_secrets(user, other_user, push):
    register_device(user, SUBSCRIPTION, user_agent=ANDROID)
    notify(user, "group.expense", {"who": "Ana", "amount": 7})
    notify(other_user, "group.expense", {"who": "Ana", "amount": 8})
    set_preference(user, "group.expense", "push", False)

    data = export_user_data(user)
    assert [d["name"] for d in data["devices"]] == ["Chrome on Android"]
    assert [n["title"] for n in data["notifications"]] == ["Ana added 7"]
    assert data["notifications"][0]["deliveries"]
    assert data["preferences"] == [{"type": "group.expense", "channel": "push", "enabled": False}]
    text = repr(data)
    for secret in (SUBSCRIPTION["endpoint"], "BNcRdreALRFX", "tBHItJI5svbpez7KI4CCXg"):
        assert secret not in text


# Password change --------------------------------------------------------------------------


def test_password_change_removes_devices(user):
    register_device(user, SUBSCRIPTION)
    user.first_name = "Alice"
    user.save()  # an ordinary save keeps them
    assert list_devices(user).count() == 1

    user.set_password("a-new-password")
    user.save()
    assert list_devices(user).count() == 0


def test_password_change_with_update_fields_and_opt_out(user, config):
    register_device(user, SUBSCRIPTION)
    user.set_password("another")
    user.save(update_fields=["first_name"])  # password not saved, so nothing changes
    assert list_devices(user).count() == 1

    with config(REMOVE_DEVICES_ON_PASSWORD_CHANGE=False):
        user.set_password("and-another")
        user.save()
    assert list_devices(user).count() == 1


def test_new_users_are_not_affected(db):
    get_user_model().objects.create_user("carol", "carol@example.com", "pw")


# Language ------------------------------------------------------------------------------------


def user_language(user):
    return {"alice": "sq", "bob": "en"}.get(user.username)


def test_each_recipient_gets_their_own_language(user, other_user, config, push):
    with config(LANGUAGE_FOR_USER="tests.test_public_api.user_language"):
        notify([user, other_user], "i18n.check")
    titles = dict(Notification.objects.values_list("user__username", "title"))
    assert titles == {"alice": "title in sq", "bob": "title in en"}
    subjects = dict(Notification.objects.values_list("user__username", "email_subject"))
    assert subjects == {"alice": "subject in sq", "bob": "subject in en"}


def test_without_the_setting_the_current_language_is_used(user, push):
    from django.utils import translation

    with translation.override("de"):
        notify(user, "i18n.check")
    assert Notification.objects.get().title == "title in de"


def broken_language(user):
    raise RuntimeError("no profile")


def test_a_failing_language_function_does_not_stop_the_notification(user, config, push):
    from django.utils import translation

    with config(LANGUAGE_FOR_USER="tests.test_public_api.broken_language"), translation.override("fr"):
        notify(user, "i18n.check")
    assert Notification.objects.get().title == "title in fr"


def test_bad_language_function_path_is_reported(config):
    from kvn_notify.checks import check_settings

    with config(LANGUAGE_FOR_USER="tests.nowhere.missing"):
        assert "kvn_notify.E005" in [p.id for p in check_settings()]
