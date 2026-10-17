# The in-app inbox

**The inbox is an optional list of past notifications that your app shows in its own pages,
with read and unread marks.** It is off by default.

A push is shown by the phone's system and is gone once dismissed. The inbox is stored by your app
and shown in your pages, like the bell icon on most websites. kvn-notify stores the list and
gives you endpoints; the bell and the list page are yours, so they match your design.

## Turn it on

1. Add `"INBOX": True` to `KVN_NOTIFY`.
2. Add `"inbox"` to the channels of each type that should appear in the list:

    ```python
    register(NotificationType(
        key="group.expense",
        channels=["push", "inbox"],
        title="{who} added {amount}",
    ))
    ```

Types without `"inbox"` never appear in the list, so short-lived alerts can stay push-only.

## Show it

=== "JavaScript"

    ```javascript
    const page = await notify.inbox.list({ unread: false, page: 1, pageSize: 20 });
    // { results: [...], count, page, next_page, unread_count }

    const unread = await notify.inbox.unreadCount();
    await notify.inbox.markRead(item.id);
    await notify.inbox.markAllRead();
    ```

    The React example's inbox:

    ```jsx
    --8<-- "examples/django-api-react/frontend/src/App.jsx:inbox"
    ```

=== "Django templates"

    ```django
    {% load kvn_notify %}
    <a href="/inbox/">Inbox ({% kvn_notify_unread_count %})</a>
    ```

    For the list itself, query the model in your view:

    ```python
    from kvn_notify.models import Notification

    Notification.objects.filter(user=request.user, in_inbox=True)[:50]
    ```

    Each has `title`, `body`, `url`, `data`, `created_at` and `read_at` (`None` when unread).

Each item from the API looks like this:

```json
{
  "id": "6f1c2e4a-8a7b-4c1e-9d55-0b2f4c7d9e10",
  "type": "group.expense",
  "title": "Ana added 12 EUR",
  "body": "",
  "url": "/groups/1",
  "data": {"group": 1},
  "read": false,
  "read_at": null,
  "created_at": "2026-10-17T12:40:09.123456+00:00"
}
```

## Mark read when a push is tapped

When a type uses both push and the inbox, tapping the push should mark the list item as read. The
service worker adds `?kvnNotificationId=<id>` to the link it opens; call this once when your app
loads:

```javascript
await notify.handleOpenedFromPush();
```

It marks the item read and removes the parameter from the address bar. Template projects get this
automatically when `INBOX` is on.

## Housekeeping

Inbox items are deleted after `INBOX_RETENTION_DAYS` (90 by default), separately from other
delivery records.
