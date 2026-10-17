# Management commands

## `notify_worker`

Sends queued notifications. Runs until stopped.

```bash
python manage.py notify_worker [--once] [--batch N] [--poll SECONDS]
```

| Option | Meaning |
| --- | --- |
| `--once` | Send everything that is due, delete old records, then exit. For cron. |
| `--batch` | Deliveries per round (default `BATCH_SIZE`, 100). |
| `--poll` | Seconds to wait when the queue is empty (default `WORKER_POLL_SECONDS`, 5). |

Prints `processed=… sent=… retried=… failed=…` after each round that did something, and each
failure's reason. Stops cleanly on Ctrl+C and `SIGTERM`. Use `-v 0` for no output.

## `notify_vapid_keys`

Creates a VAPID key pair and prints it ready for a `.env` file:

```text
VAPID_PUBLIC_KEY=BKx...
VAPID_PRIVATE_KEY=3dE...
```

Run it once per app. The format is the raw URL-safe base64 most push libraries use, so keys from
an existing app can be used as they are.

## `notify_make_badge`

Turns a logo into a status bar badge: a white symbol on a transparent 96×96 square. Needs
`pip install "kvn-notify[icons]"`.

```bash
python manage.py notify_make_badge static/logo.png [--output PATH] [--threshold 40]
```

| Option | Meaning |
| --- | --- |
| `--output` | Where to write it (default: `<logo>-badge-96.png` next to the logo). |
| `--threshold` | For logos without transparency: how different from the corner colour a pixel must be to count as part of the symbol (0–255). |
