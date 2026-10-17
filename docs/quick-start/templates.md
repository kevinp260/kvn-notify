# Quick start: Django with templates

By the end of this page, a button on your site turns notifications on, and one line of Python
sends a push to your phone or laptop. The code below comes from the
[`examples/django-templates`](https://github.com/kevinp260/kvn-notify/tree/main/examples/django-templates)
project, which you can run with `docker compose up --build`.

## 1. Install the package

```bash
pip install "kvn-notify[icons]"
```

The `icons` extra adds Pillow, used by the icon checks and the badge tool.

## 2. Create your VAPID keys

VAPID keys identify your server to the browsers' push services. Create them once per app:

```bash
python manage.py notify_vapid_keys
```

You should see two lines:

```text
VAPID_PUBLIC_KEY=BKx...
VAPID_PRIVATE_KEY=3dE...
```

Store them like any other secret, for example in your `.env` file.

!!! warning "Create keys once, then keep them"

    Every device that subscribes is tied to these keys. If you change them later, every
    existing device silently stops receiving notifications until its user turns them on again.

## 3. Add the app and its settings

In `settings.py`, add `kvn_notify` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "kvn_notify",
]
```

Then add the settings block. Read the keys from your environment in a real project:

```python
--8<-- "examples/django-templates/project/settings.py:kvn_notify"
```

What each line does:

- `BADGE` and `ICON` are static paths. The badge must be a **white symbol on a transparent
  background**, 96×96. If you only have a logo, `python manage.py notify_make_badge logo.png`
  makes one. See [Icons and badges](../guides/icons.md).
- `SITE_URL` is your public address, used for links in emails.
- `DISPATCH: "worker"` means a separate process sends the messages (step 8).
- `INBOX: True` turns on the optional in-app list. Leave it out if you do not need one.

## 4. Add the URLs and create the tables

In your root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("notify/", include("kvn_notify.urls")),
]
```

```bash
python manage.py migrate
```

You should see `Applying kvn_notify.0001_initial... OK`. Run `python manage.py check` too: any
problem with your keys or icons is reported there with a link to its fix.

## 5. Declare a notification type

Create `notification_types.py` in any of your apps. kvn-notify finds it automatically:

```python
--8<-- "examples/django-templates/demo/notification_types.py:types"
```

`title`, `body` and `url` are filled from the values you pass when sending. See
[Declaring and sending](../guides/sending.md) for every option.

## 6. Add the button and the script

In the template where users should turn notifications on:

```django
{% load kvn_notify %}

--8<-- "examples/django-templates/demo/templates/demo/home.html:button"
```

And once in your base template, just before `</body>`:

```django
{% load kvn_notify %}
{% kvn_notify_scripts %}
```

The button changes its own label between "Turn on notifications" and "Turn off notifications",
and disables itself when the browser does not support push or the user blocked it.

## 7. Add one line to your service worker

Notifications are shown by a service worker, a small script the browser keeps running in the
background. If your site already has one, add this line to it:

```javascript
--8<-- "examples/django-templates/demo/templates/demo/sw.js:import"
```

The example serves its worker from the site root (`/sw.js`) through a view, and registers it
in the base template:

```html
<script>
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
</script>
```

!!! note "No service worker yet?"

    Use the ready-made one instead: write `{% kvn_notify_scripts "default" %}` in step 6 and
    skip this step. It handles notifications only; add your own worker later if you want
    offline pages or caching.

## 8. Start the dispatcher

Notifications are saved first and sent by a separate process. In a second terminal:

```bash
python manage.py notify_worker
```

You should see `kvn-notify worker started`. In production, run it as a service next to your web
process; see [Running the dispatcher](../guides/dispatch.md) for systemd, Docker and Celery.

## 9. Send one

Anywhere in your code, usually in a view or after a model change:

```python
--8<-- "examples/django-templates/demo/views.py:send"
```

**Try it:** open your site, log in, click the button and allow notifications. Then trigger the
code above. Within a few seconds the notification appears, and the worker prints
`processed=… sent=…`.

## 10. Remove the device on logout

A device belongs to the browser, not the login. Before logging a user out, remove the device so
the next person on that browser does not receive their notifications:

```javascript
await window.kvnNotify.unsubscribe();
```

The example's base template does this in the logout form's submit handler.

## Next steps

- [Emails and templates](../guides/emails.md): change the look of emails or write your own.
- [The in-app inbox](../guides/inbox.md): show past notifications in your pages.
- [Deploying](../guides/deploying.md): HTTPS, iPhones, and moving an app that already sends push.
- Something not working? [Troubleshooting](../troubleshooting.md).
