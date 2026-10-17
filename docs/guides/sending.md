# Declaring and sending

**A notification type is declared once and sent with one line.** The type holds everything
about the message: its channels, its text, its link and how it behaves. Code that sends it only
names the type and passes the values.

## Declaring a type

Put declarations in a `notification_types.py` module in any installed app; kvn-notify imports
these modules at startup.

```python
from kvn_notify import NotificationType, register

register(
    NotificationType(
        key="leave.approved",
        channels=["email", "push"],
        title="Your leave request was approved",
        body="{leave.leave_type.name}, {dates}",
        url="/leaves/{leave.id}",
    )
)
```

| Option | Default | Meaning |
| --- | --- | --- |
| `key` | required | A unique name. Dots group related types: `leave.approved`, `leave.declined`. |
| `title` | required | The headline. |
| `body` | `""` | The text under the title. |
| `url` | `""` | Where tapping the notification, or the email's button, leads. |
| `channels` | `("push",)` | Any of `"push"`, `"email"`, `"inbox"`, or a [channel you add](custom-channels.md). |
| `fallback` | `None` | A channel used when a push reaches no device: the user has none, or every device failed. Usually `"email"`. |
| `required` | `False` | `True` ignores user preferences. Use it for security and outage alerts. |
| `email_template` | `None` | Your own email templates for this type. See [Emails](emails.md). |
| `email_subject` | the title | A different email subject. |
| `tag` | the notification id | Notifications with the same tag replace each other on the device, e.g. `"incident-{incident.id}"` so "Recovered" replaces "Down". |
| `ttl` | `PUSH_TTL` (1 hour) | Seconds the push service keeps trying to reach an offline device. |
| `urgency` | `"normal"` | `"very-low"`, `"low"`, `"normal"` or `"high"`. Phones may delay low urgency to save battery. |
| `description` | `""` | Shown on a settings screen, if you build one. |

### Filling in the text

`title`, `body`, `url`, `tag` and `email_subject` are Python format strings filled from the
context you pass to `notify()`. Attribute access works: `{order.customer.first_name}`.
The recipient is always available as `{recipient}`.

When a format string is not enough, pass a function that takes the context and returns text:

```python
register(
    NotificationType(
        key="group.expense",
        channels=["push", "inbox"],
        title=lambda ctx: f"{ctx['who']} added {ctx['amount']:.2f} {ctx['currency']}",
    )
)
```

A missing value raises an error naming the field and the value, so a typo shows up the first time
you send, not in a user's inbox.

## Sending

```python
from kvn_notify import notify

notify(leave.employee.user, "leave.approved", {"leave": leave, "dates": "3–7 Nov"})
```

`notify()` returns as soon as the notification is saved. It is sent after your database
transaction commits, so a change that rolls back never produces a message.

### Recipients

| You pass | Who receives it |
| --- | --- |
| A user | That user |
| A list or queryset of users | Each of them, once |
| An email address string | That address, by email only. Useful for alert inboxes and contact forms. |
| A mix of users and addresses | Each of them |

Push and the inbox need a user account. An email address recipient only receives channels that
can reach it, and a type's `fallback` is used straight away.

### Options

```python
notify(
    recipients,
    "monitor.down",
    {"monitor": monitor, "cause": cause},
    channels=["email"],  # override the type's channels for this call only
    dedupe_key=f"down-{incident.pk}",
    data={"monitor_id": monitor.pk},
)
```

- **`dedupe_key`**: a second call with the same key for the same recipient does nothing. Use it
  for reminders and anything a scheduled job might trigger twice.
- **`data`**: extra JSON values stored with the notification and returned by the inbox API, for
  your frontend to use.
- **`channels`**: rarely needed. Prefer changing the type.

## User preferences

Users can turn a type off per channel. kvn-notify stores and applies the choice; whether you
offer a settings screen is up to you.

```python
from kvn_notify.api import get_preferences, set_preference

set_preference(user, "leave.approved", "email", False)
get_preferences(user)
# [{"type": "leave.approved", "description": "...", "required": False,
#   "channels": {"email": False, "push": True}}, ...]
```

Frontends use `GET` and `POST /notify/preferences/` for the same thing; see
[HTTP endpoints](../reference/endpoints.md). Types with `required=True` are always sent.

## What happens after `notify()`

1. One **notification** row is saved per recipient, with its final title, body and link.
2. One **delivery** row is saved per channel, and for push one per device.
3. After your transaction commits, the dispatcher sends each delivery. Temporary errors are
   retried after 1, 2, 4 and 8 minutes. A device the push service reports as gone is switched
   off.
4. When no device took a push and the type has a `fallback`, a fallback delivery is created.

Everything is visible in the Django admin under **Notifications**, including each attempt's
error. The **Retry the selected deliveries now** action queues failed ones again.
