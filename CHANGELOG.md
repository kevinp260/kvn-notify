# Changelog

All notable changes are listed here. Versions follow [semantic versioning](https://semver.org/):
a breaking change bumps the first number.

## Unreleased

### Added

- `notify()` and `NotificationType`: declare a notification once, send it with one line.
- Channels: Web Push, email (HTML + plain text) and an optional in-app inbox.
- Database queue with retries, email fallback for push, deduplication and user preferences.
- `fallback_recipients`: tell an address only if no device of anyone took the push.
- `cancel()` for notifications that are no longer relevant, and `delivery_sent` /
  `delivery_failed` signals.
- Dispatch modes: `worker` (`notify_worker`), `celery` and `inline`.
- Endpoints for subscribing devices, test pushes, preferences and the inbox, with session,
  Django REST framework or custom authentication, and an optional `PERMISSION` check (e.g. 2FA).
- Startup checks for VAPID keys and notification icons; `notify_make_badge` and
  `notify_vapid_keys` commands.
- `kvn-notify-web`: browser client and service worker handlers for any frontend, plus
  template tags for Django template projects.
- Readable device names ("Chrome on Android") in `PushSubscription.device_name` and `label`,
  with an optional `device_name` when subscribing.
- CSRF works with `CSRF_COOKIE_HTTPONLY = True`: the client falls back to the page's token,
  and accepts a `csrfToken` option.

### Fixed

- Django REST framework session logins no longer fail with a JSON body.
