# Settings

All settings live in one dict in your `settings.py`. Every key is optional; anything left out uses
the default below.

```python
KVN_NOTIFY = {
    "VAPID_PUBLIC_KEY": env("VAPID_PUBLIC_KEY"),
    "VAPID_PRIVATE_KEY": env("VAPID_PRIVATE_KEY"),
    "VAPID_SUBJECT": "mailto:you@example.com",
}
```

## Web Push

| Setting | Default | Meaning |
| --- | --- | --- |
| `VAPID_PUBLIC_KEY` | `""` | Public key from `notify_vapid_keys`. Sent to browsers. |
| `VAPID_PRIVATE_KEY` | `""` | Private key from `notify_vapid_keys`. Keep it secret. |
| `VAPID_SUBJECT` | `""` | `"mailto:you@example.com"` or your site's `https://` URL. |
| `ICON` | `""` | Large notification image: a static path or a URL. At least 192×192. |
| `BADGE` | `""` | Status bar symbol: a static path or a URL. White on transparent, 96×96. |
| `STRICT_ICONS` | `False` | Turn the icon warnings into errors, to fail CI or a deploy. |
| `PUSH_TTL` | `3600` | Seconds a push service keeps trying to reach an offline device. A type's `ttl` overrides it. |
| `PUSH_TIMEOUT` | `10` | Seconds to wait for the push service to answer. |
| `VALIDATE_PUSH_ENDPOINTS` | `True` | Refuse device addresses that are not `https` or point at private networks. Keep it on in production. |

## Sending

| Setting | Default | Meaning |
| --- | --- | --- |
| `DISPATCH` | `"worker"` | `"worker"`, `"celery"` or `"inline"`. See [Running the dispatcher](../guides/dispatch.md). |
| `MAX_ATTEMPTS` | `5` | Attempts before a delivery fails for good. |
| `RETRY_BASE_SECONDS` | `60` | First wait before a retry; it doubles each time. |
| `BATCH_SIZE` | `100` | Deliveries sent per round. |
| `WORKER_POLL_SECONDS` | `5` | How long `notify_worker` waits when the queue is empty. |
| `STALE_CLAIM_SECONDS` | `600` | When a delivery stuck "sending" (a crashed dispatcher) goes back in the queue. |

## Login and endpoints

| Setting | Default | Meaning |
| --- | --- | --- |
| `AUTH` | `"auto"` | `"auto"`, `"session"`, `"drf"`, or a dotted path to your function. See [Logins](../guides/login.md). |
| `INBOX` | `False` | Turn on the in-app list and its endpoints. |

## Email

| Setting | Default | Meaning |
| --- | --- | --- |
| `SITE_URL` | `""` | Your public origin, e.g. `"https://app.example.com"`, for links in emails. |
| `EMAIL["FROM"]` | `DEFAULT_FROM_EMAIL` | Sender address. |
| `EMAIL["BRAND_NAME"]` | `""` | Shown at the top of emails when there is no logo. |
| `EMAIL["LOGO_URL"]` | `""` | Full URL of a logo for the top of emails. |
| `EMAIL["PRIMARY_COLOR"]` | `"#2563EB"` | Button colour. |
| `EMAIL["FOOTER_TEXT"]` | `""` | Small text under every email. |

Emails go through Django's own email settings (`EMAIL_BACKEND`, `EMAIL_HOST`, ...).

## Housekeeping

| Setting | Default | Meaning |
| --- | --- | --- |
| `DELIVERY_RETENTION_DAYS` | `90` | Delete finished notifications older than this. `0` keeps them. |
| `INBOX_RETENTION_DAYS` | `90` | The same for inbox items. |
