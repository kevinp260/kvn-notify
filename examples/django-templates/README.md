# Example: Django with templates

A small Django site that turns on push notifications with template tags and sends
one notification through push, email and the in-app inbox.

## Run it

```bash
docker compose up --build
```

Open <http://localhost:8000>, log in as **demo** / **demo**, click **Turn on notifications**,
then **Ship a pretend order**. The push arrives within a few seconds; the email is printed in
the `worker` container's output.

Push needs a secure page: `localhost` counts as secure, a LAN address such as
`192.168.1.10` does not.

## Without Docker

```bash
pip install "kvn-notify[icons]"
python manage.py migrate && python manage.py seed_demo
python manage.py runserver          # terminal 1
python manage.py notify_worker      # terminal 2
```

## Where to look

| File | What it shows |
| --- | --- |
| `project/settings.py` | The `KVN_NOTIFY` settings |
| `project/urls.py` | Including `kvn_notify.urls` |
| `demo/notification_types.py` | Declaring a notification type |
| `demo/views.py` | Sending it with `notify()` |
| `demo/templates/demo/home.html` | The enable button |
| `demo/templates/demo/base.html` | Loading the script, and unsubscribing on logout |
| `demo/templates/demo/sw.js` | The one line the service worker needs |
