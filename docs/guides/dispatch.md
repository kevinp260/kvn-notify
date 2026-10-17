# Running the dispatcher

**Notifications are saved first and sent by a dispatcher afterwards, so a failed send is retried
instead of lost.** The `DISPATCH` setting picks how the dispatcher runs. It does not force Celery
on anyone.

| `DISPATCH` | How it runs | Good for |
| --- | --- | --- |
| `"worker"` (default) | `python manage.py notify_worker` runs as its own process and checks the queue every few seconds | Most projects |
| `"celery"` | A Celery task sends right after commit; a periodic task picks up retries | Projects that already run Celery |
| `"inline"` | Sends right after commit, inside the web request; a cron entry handles retries | Small sites, local development |

## Worker

```bash
python manage.py notify_worker
```

It sends what is due, waits `WORKER_POLL_SECONDS` (5) when the queue is empty, deletes old records
once an hour, and stops cleanly on Ctrl+C or `SIGTERM`.

=== "Docker Compose"

    ```yaml
    services:
      web:
        command: gunicorn project.wsgi
      notify-worker:
        image: same-as-web
        command: python manage.py notify_worker
        restart: unless-stopped
    ```

=== "systemd"

    ```ini
    # /etc/systemd/system/myapp-notify.service
    [Unit]
    Description=myapp notifications
    After=network.target

    [Service]
    WorkingDirectory=/srv/myapp
    ExecStart=/srv/myapp/.venv/bin/python manage.py notify_worker
    Restart=always
    User=myapp
    EnvironmentFile=/srv/myapp/.env

    [Install]
    WantedBy=multi-user.target
    ```

    ```bash
    sudo systemctl enable --now myapp-notify
    ```

=== "Cron, no long-running process"

    ```cron
    * * * * * cd /srv/myapp && .venv/bin/python manage.py notify_worker --once
    ```

    Sends at most once a minute. Fine with `"inline"` mode, where cron only handles retries.

Several workers can run side by side on PostgreSQL or MySQL: each delivery is locked while it is
sent, so none is sent twice. On SQLite run one.

## Celery

```bash
pip install "kvn-notify[celery]"
```

```python
KVN_NOTIFY = {"DISPATCH": "celery", ...}

CELERY_BEAT_SCHEDULE = {
    "kvn-notify-sweep": {"task": "kvn_notify.process_due", "schedule": 60.0},
    "kvn-notify-cleanup": {"task": "kvn_notify.cleanup", "schedule": 3600.0},
}
```

Make sure your Celery app discovers tasks from installed apps (`app.autodiscover_tasks()`). The
sweep matters: it sends retries, and anything queued while the broker was down.

## Inline

```python
KVN_NOTIFY = {"DISPATCH": "inline", ...}
```

The first attempt happens in the request that called `notify()`, after the transaction commits.
Each push takes one HTTP call per device, so keep this for small sites. Add the cron entry above
so retries happen.

## Retries and failures

| What happened | What kvn-notify does |
| --- | --- |
| Timeout, push service error 5xx or 429, mail server unreachable | Retries after 1, 2, 4, then 8 minutes (`RETRY_BASE_SECONDS`), up to `MAX_ATTEMPTS` (5) |
| Push service answers 404 or 410 | The device unsubscribed or the app was removed: the device is switched off |
| Push service answers 400, 401 or 403 | Usually the wrong VAPID keys: fails without retrying |
| Mail server refuses the address | Fails without retrying |
| A dispatcher crashed while sending | The delivery goes back in the queue after `STALE_CLAIM_SECONDS` (10 minutes) |

Failed deliveries stay visible in the admin with their error. Select them and use **Retry the
selected deliveries now** once the cause is fixed.
