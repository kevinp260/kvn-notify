# Adding a channel (SMS and others)

**A channel is a small class with two methods: one creates deliveries, the other makes one
attempt.** Queueing, retries, preferences and the admin come for free.

## The two methods

```python
from kvn_notify.channels import Channel, SendResult


class SmsChannel(Channel):
    name = "sms"

    def create_deliveries(self, notification):
        """Create Delivery rows. Return [] when this channel cannot reach the recipient."""
        from kvn_notify.models import Delivery

        phone = getattr(notification.user, "phone_number", "") if notification.user_id else ""
        if not phone:
            return []
        return [Delivery.objects.create(notification=notification, channel=self.name)]

    def send(self, delivery):
        """One attempt. Never raise: report the outcome."""
        notification = delivery.notification
        try:
            sms_provider.send(to=notification.user.phone_number, text=notification.title)
        except sms_provider.TemporaryError as exc:
            return SendResult.retry(str(exc))  # tried again later, with growing waits
        except sms_provider.InvalidNumber as exc:
            return SendResult.failed(str(exc))  # given up, visible in the admin
        return SendResult.sent()
```

## Registering it

Register the channel when your app starts:

```python
# yourapp/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "yourapp"

    def ready(self):
        from kvn_notify.channels import register_channel

        from yourapp.channels import SmsChannel

        register_channel(SmsChannel())
```

Then use it like any built-in channel:

```python
register(
    NotificationType(
        key="login.code",
        channels=["sms"],
        required=True,
        title="Your login code is {code}",
    )
)
```

`manage.py check` reports a type that names a channel nobody registered (E004).

## Good to know

- `send()` runs in the dispatcher, not in the request, so a slow provider does not slow your pages.
- The notification's `title`, `body`, `url` and `data` are already filled in when `send()` runs.
- Keep secrets such as provider API keys in your own settings, not in `KVN_NOTIFY`.
