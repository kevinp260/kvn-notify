# kvn-notify

**Push notifications and emails for Django. Declared once, sent with one line, never lost.**

[![PyPI](https://img.shields.io/pypi/v/kvn-notify)](https://pypi.org/project/kvn-notify/)
[![Python](https://img.shields.io/pypi/pyversions/kvn-notify)](https://pypi.org/project/kvn-notify/)
[![Django 5.1+](https://img.shields.io/badge/Django-5.1%2B-0C4B33)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/kevinp260/kvn-notify/blob/main/LICENSE)
[![Tests](https://github.com/kevinp260/kvn-notify/actions/workflows/tests.yml/badge.svg)](https://github.com/kevinp260/kvn-notify/actions/workflows/tests.yml)

Every Django app that sends Web Push ends up rebuilding the same plumbing: VAPID keys,
device subscriptions, a service worker, retries, dead devices, broken icons. kvn-notify
is that plumbing, done once, so you write the notification and not the delivery code.

```python
from kvn_notify import notify

notify(user, "order.shipped", {"order": order})
```

- **One call, every channel.** Push, email and an optional in-app list follow the
  notification type you declared, not each call site.
- **Nothing gets lost.** Saved inside your transaction, sent by a queue that retries
  and falls back to email when no device takes the push.
- **Any frontend.** Django templates, or React, Vue, Svelte and plain JS through a
  small client with no dependencies.
- **Sessions or tokens.** Uses your Django REST framework login, JWT included, or
  plain Django sessions.
- **No extra servers.** Runs on your own database. Celery is optional.
- **No white squares.** Startup checks catch broken notification icons before your
  users see them.
- **Emails that look right by default**, with templates you can override.

[Documentation](https://kevinp260.github.io/kvn-notify/) ·
[Quick start](https://kevinp260.github.io/kvn-notify/quick-start/) ·
[Changelog](https://kevinp260.github.io/kvn-notify/changelog/)

## Install

```bash
pip install kvn-notify            # add [drf], [celery] or [icons] as needed
python manage.py notify_vapid_keys
```

```python
# settings.py
INSTALLED_APPS += ["kvn_notify"]

KVN_NOTIFY = {
    "VAPID_PUBLIC_KEY": env("VAPID_PUBLIC_KEY"),
    "VAPID_PRIVATE_KEY": env("VAPID_PRIVATE_KEY"),
    "VAPID_SUBJECT": "mailto:you@example.com",
    "BADGE": "icons/badge-96.png",  # white symbol on transparent, 96x96
    "ICON": "icons/icon-192.png",
    "SITE_URL": "https://app.example.com",
}

# urls.py
urlpatterns += [path("notify/", include("kvn_notify.urls"))]
```

```bash
python manage.py migrate
python manage.py notify_worker     # or DISPATCH "celery" / "inline"
```

## Declare a notification once

```python
# yourapp/notification_types.py  (found automatically)
from kvn_notify import NotificationType, register

register(
    NotificationType(
        key="order.shipped",
        channels=["push", "email"],
        title="Your order is on its way",
        body="Order {order.number} left the warehouse.",
        url="/orders/{order.id}",
    )
)
```

## Turn notifications on in the browser

Django templates:

```django
{% load kvn_notify %}
{% kvn_notify_button %}
{% kvn_notify_scripts %}
```

and one line in your service worker: `importScripts("/static/kvn_notify/sw.js");`

Any other frontend:

```bash
npm install kvn-notify-web
```

```js
import { createClient } from "kvn-notify-web";

const notify = createClient({ baseUrl: "/notify" });
button.onclick = () => notify.subscribe();
```

```js
// sw.js
import { registerPushHandlers } from "kvn-notify-web/sw";
registerPushHandlers();
```

The full guides cover tokens and sessions, email templates, the in-app inbox,
dispatch modes and deployment: <https://kevinp260.github.io/kvn-notify/>.

## License

MIT. Free to use in personal, open source and commercial projects.
