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
- One CSRF rule for every login setup: a changing request without a token header
  (`TOKEN_HEADERS`, default `Authorization` and `X-Session-Token`) must pass the CSRF check,
  whatever `AUTH` is. `ENFORCE_CSRF = False` opts out (warning W010). Tested against Django
  sessions, DRF sessions, Simple JWT, DRF tokens, a proxy, dj-rest-auth's JWT cookie and custom
  functions. W011 warns about a script-readable session cookie in production.
- Public functions for apps with their own endpoints: `register_device`, `remove_device`,
  `remove_devices`, `list_devices`, `send_test` and `kvn_notify.inbox`. In the browser,
  `createBrowserSubscription()` and `removeBrowserSubscription()`.
- `LANGUAGE_FOR_USER`: each recipient's push and email are rendered in their language.
- `REMOVE_DEVICES_ON_PASSWORD_CHANGE` (on by default): a password change removes the user's
  devices, as Django ends their other sessions.
- `anotify()` and `acancel()` for async code; `export_user_data(user)` for data exports.
- `kvn-notify-web`: `needsInstall()` for iPhones and iPads (the button tag shows the hint),
  `onUnauthorized` to refresh an expired token and retry, and `tokenHeaders`.
- A device list for "your devices" pages: `GET subscriptions/` lists the user's devices and
  `DELETE subscriptions/<id>/` removes one. In the browser, `client.devices.list()` marks this
  browser's own device (`current`), and `client.devices.remove()` also drops this browser's
  subscription when it removes its own. Push addresses are never returned, only a hash.
- `INACTIVE_DEVICE_RETENTION_DAYS` (30 by default): devices the push service rejected for good
  are deleted this long after, by the worker's hourly cleanup.
- A refused CSRF token is reported as `"code": "csrf_failed"` in the error body. In the browser,
  `csrfToken` may be an async function (fetch the token from your API once) and
  `onCsrfFailure` renews it and retries once; such errors have `code` `"csrf"`.

### Changed (for apps already on a pre-release commit)

- A custom `AUTH` function now gets the CSRF check too unless the request has a token header.
  List your login header in `TOKEN_HEADERS` if it isn't `Authorization` or `X-Session-Token`.
- Changing a password removes that user's devices. Set `REMOVE_DEVICES_ON_PASSWORD_CHANGE = False`
  to keep the old behaviour.

### Fixed

- Django REST framework session logins no longer fail with a JSON body.
- `notify_worker` keeps running when the database restarts or is not migrated yet: it waits,
  reconnects and tries again instead of erroring on every round or exiting.
