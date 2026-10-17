# kvn-notify

**Push notifications and emails for Django. Declared once, sent with one line, never lost.**

Every Django app that sends Web Push ends up rebuilding the same plumbing: VAPID keys,
device subscriptions, a service worker, retries, dead devices, broken icons. kvn-notify is that
plumbing, done once, so you write the notification and not the delivery code.

```python
from kvn_notify import notify

notify(user, "order.shipped", {"order": order})
```

## What you get

| Feature | What it means |
| --- | --- |
| **One call, every channel** | Push, email and an optional in-app list follow the notification type you declared, not each call site. |
| **Nothing gets lost** | Messages are saved inside your transaction and sent by a queue that retries, and falls back to email when no device takes the push. |
| **Any frontend** | Django templates, or React, Vue, Svelte and plain JS through a small client with no dependencies. |
| **Sessions or tokens** | Uses your Django REST framework login (JWT included) or plain Django sessions. |
| **No extra servers** | Runs on your own database. Celery is optional. |
| **No white squares** | Startup checks catch broken notification icons before your users see them. |
| **Emails that look right** | A clean default layout, with templates you can override at three levels. |

## How it fits together

Your app decides *when* something happens and calls `notify()`. The package decides *how* it
reaches the person: it writes the message, stores the devices, sends, retries and falls back.
The browser only asks for permission, registers the device and shows what the server sends.

| Part | Where it runs | Package |
| --- | --- | --- |
| Notification types, `notify()`, the queue, sending, retries, email | Your Django server | `kvn-notify` (PyPI) |
| Asking permission, registering the device | The page | `kvn-notify-web` (npm), or the bundled script for template projects |
| Showing the notification, opening the link | The service worker | `kvn-notify-web/sw`, or the bundled `sw.js` |

## Where to start

<div class="grid cards" markdown>

- **[Django with templates](quick-start/templates.md)**

    Your pages are Django templates. Three template tags and one line in your service worker.

- **[Django API + any frontend](quick-start/frontend.md)**

    React, Vue, Svelte or anything else talks to Django over an API, with sessions or tokens.

</div>

Both quick starts follow a runnable example project in the
[`examples/`](https://github.com/kevinp260/kvn-notify/tree/main/examples) folder, so you can
compare your code with working code at every step.

## Requirements

- Python 3.10+ and Django 5.1+
- HTTPS in production (browsers only allow push on secure pages; `localhost` counts as secure)
- PostgreSQL or MySQL recommended for several dispatchers side by side; SQLite works with one
