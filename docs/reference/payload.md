# Push message format

This is the contract between the server (`kvn-notify`) and the service worker
(`kvn-notify-web`). Anyone writing their own service worker or a native client can follow it.

Every push carries one JSON object, encrypted by the browser's push service:

```json
{
  "v": 1,
  "id": "6f1c2e4a-8a7b-4c1e-9d55-0b2f4c7d9e10",
  "type": "monitor.down",
  "title": "[DOWN] Shop",
  "body": "Timeout after 10 seconds",
  "url": "/monitors/4",
  "tag": "incident-9",
  "icon": "/static/icons/icon-192.png",
  "badge": "/static/icons/badge-96.png",
  "inbox": false
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `v` | number | Format version. Changes only when a field is removed or changes meaning. |
| `id` | string | The notification's id. Used to mark it read in the inbox. |
| `type` | string | The notification type key the app registered. |
| `title` | string | Up to 200 characters. |
| `body` | string | Up to 1000 characters, may be empty. |
| `url` | string | Link to open when tapped. Relative to the site, or absolute. |
| `tag` | string | Notifications with the same tag replace each other. Defaults to `id`. |
| `icon` | string | Large image URL, or empty. |
| `badge` | string | Status bar symbol URL (white on transparent), or empty. |
| `inbox` | boolean | `true` when the notification is also in the in-app list. |

A service worker following this format:

- shows `title`, `body`, `icon`, `badge` and `tag` with `showNotification`;
- opens `url` on tap, only if it is on the site's own origin;
- when `inbox` is `true`, adds `kvnNotificationId=<id>` to the opened link so the page can mark it
  read (`client.handleOpenedFromPush()` does this).

New fields may be added within version 1; ignore fields you do not know.
