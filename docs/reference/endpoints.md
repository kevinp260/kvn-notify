# HTTP endpoints

The JSON endpoints in `kvn_notify.urls`, shown here under `/notify/`. The JavaScript client calls
them for you; this page is for anyone writing their own client.

Every endpoint except the VAPID key needs a logged-in user (see [Logins](../guides/login.md)).
Errors are JSON: `{"error": "message"}` with status `400`, `401`, `403`, `404`, `405`, `409` or `503`.
A `403` for a missing or wrong CSRF token also has `"code": "csrf_failed"`, so a client can fetch a
fresh token and try again.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `vapid-key/` | The public key browsers need to subscribe |
| GET | `sw.js` | A ready-made service worker, for apps without one |
| GET | `subscriptions/` | The user's devices |
| POST | `subscriptions/` | Save this device |
| DELETE | `subscriptions/` | Remove this device |
| DELETE | `subscriptions/<id>/` | Remove one of the user's devices |
| POST | `test/` | Send a test push to the user's devices |
| GET, POST | `preferences/` | Read or change the user's preferences |
| GET | `inbox/` | The user's inbox (when `INBOX` is on) |
| GET | `inbox/unread-count/` | Unread count |
| POST | `inbox/<id>/read/` | Mark one as read |
| POST | `inbox/read-all/` | Mark all as read |

## `GET vapid-key/`

```json
{"public_key": "BKx..."}
```

`503` when `VAPID_PUBLIC_KEY` is not set.

## `GET subscriptions/`

The logged-in user's devices, newest first, for a "your devices" page:

```json
{"results": [
  {"id": 12, "name": "Chrome on Android", "active": true,
   "endpoint_hash": "9f86d08...", "created_at": "2026-10-19T08:12:01+00:00",
   "last_success_at": "2026-10-19T16:40:12+00:00"}
]}
```

Push addresses and keys are never returned. `endpoint_hash` is the SHA-256 of the address (hex),
so a browser can recognise its own device by hashing its subscription's `endpoint`; the
JavaScript client does this and sets `current`. `active` is `false` once the push service has
rejected the device for good; such devices are deleted after `INACTIVE_DEVICE_RETENTION_DAYS`.

## `POST subscriptions/`

Send the browser's subscription as it is (`subscription.toJSON()`):

```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/...",
  "keys": {"p256dh": "BNcR...", "auth": "tBHI..."},
  "device_name": "Kevin's phone"
}
```

`device_name` is optional. Without it the device is named from the browser, such as
"Chrome on Android" or "Safari on iPhone".

`201 {"id": 12, "created": true}` for a new device, `200` with `"created": false` for a known one.
A known device is moved to the logged-in user. `400` when the endpoint is not `https`, points at a
private network, or a key is missing.

## `DELETE subscriptions/`

```json
{"endpoint": "https://fcm.googleapis.com/fcm/send/..."}
```

`204`. Only the logged-in user's own device is removed.

## `DELETE subscriptions/<id>/`

Removes one of the user's devices by its `id` from the list, e.g. a lost phone. `204`, or `404`
for a device that is not the user's. To remove the browser you are in, use `DELETE subscriptions/`
(or `client.unsubscribe()`), which also lets the browser drop its own subscription.

## `POST test/`

`202 {"devices": 2}`, or `409` when the user has no active device.

## `GET preferences/` and `POST preferences/`

```json
{"results": [
  {"type": "leave.approved", "description": "...", "required": false,
   "channels": {"email": true, "push": false}}
]}
```

`POST` with `{"type": "leave.approved", "channel": "push", "enabled": false}` changes one and
returns the same list.

## `GET inbox/`

Query parameters: `page` (from 1), `page_size` (1–100, default 20), `unread=1` for unread only.

```json
{
  "results": [{"id": "6f1c...", "type": "group.expense", "title": "Ana added 12 EUR",
               "body": "", "url": "/groups/1", "data": {}, "read": false,
               "read_at": null, "created_at": "2026-10-17T12:40:09+00:00"}],
  "count": 31,
  "page": 1,
  "next_page": 2,
  "unread_count": 4
}
```

## `GET inbox/unread-count/`

`{"unread_count": 4}`

## `POST inbox/<id>/read/` and `POST inbox/read-all/`

`204`, or `404` for a notification that is not the user's. `read-all/` returns `{"marked": 4}`.
