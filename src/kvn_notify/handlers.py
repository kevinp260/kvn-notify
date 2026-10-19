"""Keeping devices in step with account security.

When a user's password changes, Django ends their sessions elsewhere; with
KVN_NOTIFY["REMOVE_DEVICES_ON_PASSWORD_CHANGE"] (on by default) their push
devices go too. A thief's or old phone then stops getting notifications, and the
user turns them on again on the devices they still use.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save

from kvn_notify.conf import notify_settings


def _note_password_change(sender, instance, raw=False, update_fields=None, **kwargs):
    instance._kvn_notify_password_changed = False
    if raw or instance.pk is None or instance._state.adding:
        return
    if update_fields is not None and "password" not in update_fields:
        return
    if not notify_settings.REMOVE_DEVICES_ON_PASSWORD_CHANGE:
        return
    old = sender._default_manager.filter(pk=instance.pk).values_list("password", flat=True).first()
    instance._kvn_notify_password_changed = old is not None and old != instance.password


def _remove_devices_after_password_change(sender, instance, created=False, raw=False, **kwargs):
    if raw or created or not getattr(instance, "_kvn_notify_password_changed", False):
        return
    instance._kvn_notify_password_changed = False
    from kvn_notify.devices import remove_devices

    remove_devices(instance)


def connect() -> None:
    user_model = get_user_model()
    pre_save.connect(_note_password_change, sender=user_model, dispatch_uid="kvn_notify_password_pre")
    post_save.connect(
        _remove_devices_after_password_change, sender=user_model, dispatch_uid="kvn_notify_password_post"
    )
