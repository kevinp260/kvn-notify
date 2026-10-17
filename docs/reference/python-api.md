# Python API

Everything an app imports. The rest of the package is internal and may change between versions.

## `notify()`

```python
from kvn_notify import notify

notify(recipients, type_key, context=None, *, channels=None, dedupe_key=None, data=None)
```

| Argument | Type | Meaning |
| --- | --- | --- |
| `recipients` | user, email address, or a list or queryset of either | Who receives it. Duplicates are sent once. |
| `type_key` | `str` | A registered type's key. |
| `context` | `dict` | Values used in the type's text and email templates. |
| `channels` | list of `str` | Use these channels instead of the type's, for this call only. |
| `dedupe_key` | `str` | A repeat call with the same key for the same recipient does nothing. |
| `data` | `dict` | Extra JSON values stored with the notification, returned by the inbox API. |

Returns the list of `Notification` objects created; recipients skipped by `dedupe_key` are not in
it. Sending starts after the current transaction commits.

Raises `UnknownNotificationType` for an unregistered key, `ImproperlyConfiguredType` when the
context lacks a value the text needs, `ValueError` for an invalid email address and `TypeError`
for a recipient that is neither a user nor a string.

## `NotificationType` and `register()`

```python
from kvn_notify import NotificationType, register

register(NotificationType(key="...", title="...", ...))
```

All options are listed in [Declaring and sending](../guides/sending.md#declaring-a-type).
`register()` returns the type. Registering the same key twice with different options raises
`ImproperlyConfiguredType`.

## Preferences

```python
from kvn_notify.api import get_preferences, set_preference

set_preference(user, type_key, channel, enabled)   # returns the Preference
get_preferences(user)                              # every type with its channels on or off
```

## Channels

```python
from kvn_notify.channels import Channel, SendResult, register_channel
```

See [Adding a channel](../guides/custom-channels.md).

## Models

Read them like any Django model, for example to build your own inbox page or reports.

| Model | Holds |
| --- | --- |
| `kvn_notify.models.Notification` | One message to one recipient: `type`, `user` or `email`, `title`, `body`, `url`, `data`, `in_inbox`, `read_at`, `created_at` |
| `kvn_notify.models.Delivery` | One channel (and for push one device) of a notification: `channel`, `status`, `attempts`, `next_attempt_at`, `sent_at`, `last_error`, `is_fallback` |
| `kvn_notify.models.PushSubscription` | One subscribed browser or installed app: `user`, `endpoint`, `active`, `user_agent`, `last_success_at` |
| `kvn_notify.models.Preference` | A user's choice: `user`, `type`, `channel`, `enabled` |

## Exceptions

All in `kvn_notify.exceptions`, all subclasses of `KvnNotifyError`:
`UnknownNotificationType`, `ImproperlyConfiguredType`, `UnknownChannel`.
