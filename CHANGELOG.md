# Changelog

All notable changes are listed here. Versions follow [semantic versioning](https://semver.org/):
a breaking change bumps the first number.

## Unreleased

### Added

- `notify()` and `NotificationType`: declare a notification once, send it with one line.
- Channels: Web Push, email (HTML + plain text) and an optional in-app inbox.
- Database queue with retries, email fallback for push, deduplication and user preferences.
- Dispatch modes: `worker` (`notify_worker`), `celery` and `inline`.
- Endpoints for subscribing devices, test pushes, preferences and the inbox, with session,
  Django REST framework or custom authentication.
- Startup checks for VAPID keys and notification icons; `notify_make_badge` and
  `notify_vapid_keys` commands.
- `kvn-notify-web`: browser client and service worker handlers for any frontend, plus
  template tags for Django template projects.
