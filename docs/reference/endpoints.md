# HTTP endpoints

The JSON endpoints in `kvn_notify.urls`, shown here under `/notify/`. The JavaScript client calls
them for you; this page is for anyone writing their own client.

Every endpoint except the VAPID key needs a logged-in user (see [Logins](../guides/login.md)).
Errors are JSON: `{"error": "message"}` with status `400`, `401`, `403`, `404`, `405`, `409` or `503`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `vapid-key/` | The public key browsers need to subscribe |
| GET | `sw.js` | A ready-made service worker, for apps without one |
| POST | `subscriptions/` | Save this device |
| DELETE | `subscriptions/` | Remove this device |
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

## `POST subscriptions/`

Send the browser's subscription as it is (`subscription.toJSON()`):

```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/...",
  "keys": {"p256dh": "BNcR...", "auth": "tBHI..."}
}
```

`201 {"id": 12, "created": true}` for a new device, `200` with `"created": false` for a known one.
A known device is moved to the logged-in user. `400` when the endpoint is not `https`, points at a
private network, or a key is missing.

## `DELETE subscriptions/`

```json
{"endpoint": "https://fcm.googleapis.com/fcm/send/..."}
```

`204`. Only the logged-in user's own device is removed.

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
