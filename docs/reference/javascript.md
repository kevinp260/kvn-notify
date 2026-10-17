# JavaScript (kvn-notify-web)

```bash
npm install kvn-notify-web
```

No dependencies, no framework, TypeScript types included. Django template projects get the same
code as a plain script through `{% kvn_notify_scripts %}`.

## `createClient(options)`

```javascript
import { createClient } from "kvn-notify-web";

const notify = createClient({ baseUrl: "/notify" });
```

| Option | Default | Meaning |
| --- | --- | --- |
| `baseUrl` | `"/notify"` | Where `kvn_notify.urls` is included. |
| `getHeaders` | none | Function returning extra headers per request, e.g. `Authorization`. May be async. |
| `credentials` | `"same-origin"` | `"include"` for a cookie session on another origin. |
| `csrfCookieName` | `"csrftoken"` | Django's CSRF cookie, sent as `X-CSRFToken` when there is no `Authorization` header. |
| `serviceWorker` | none | URL of a service worker to register, for apps without their own. |
| `readyTimeout` | `10000` | Milliseconds to wait for a service worker before failing. |

## The client

| Function | Returns | Notes |
| --- | --- | --- |
| `permission()` | `"granted"`, `"denied"`, `"default"` or `"unsupported"` | |
| `isSupported()` | `boolean` | `false` in browsers without Web Push, e.g. iPhone Safari before "Add to Home Screen" |
| `isSubscribed()` | `Promise<boolean>` | |
| `subscribe()` | `Promise<PushSubscription>` | Call it from a click. Asks permission, subscribes, saves the device. |
| `unsubscribe()` | `Promise<boolean>` | Call it before logging out. |
| `sendTest()` | `Promise<{devices}>` | |
| `preferences.list()` | `Promise<{results}>` | |
| `preferences.set(type, channel, enabled)` | `Promise<{results}>` | |
| `inbox.list({unread, page, pageSize})` | `Promise<InboxPage>` | |
| `inbox.unreadCount()` | `Promise<number>` | |
| `inbox.markRead(id)` | `Promise<null>` | |
| `inbox.markAllRead()` | `Promise<{marked}>` | |
| `handleOpenedFromPush()` | `Promise<string \| null>` | Call on page load when using the inbox. |

## Errors

Every failure is a `KvnNotifyError` with a `code`:

| `code` | When |
| --- | --- |
| `"unsupported"` | The browser has no Web Push. |
| `"permission-denied"` | The user did not allow notifications. |
| `"no-service-worker"` | No service worker covers the page within `readyTimeout`. |
| `"http"` | The server answered with an error; `status` and `message` hold its details. |

```javascript
try {
  await notify.subscribe();
} catch (error) {
  if (error.code === "permission-denied") showHint("Allow notifications in your browser settings.");
  else throw error;
}
```

## Service worker: `kvn-notify-web/sw`

```javascript
import { registerPushHandlers } from "kvn-notify-web/sw";

registerPushHandlers({ defaultTitle: "My app" });
```

| Option | Meaning |
| --- | --- |
| `defaultTitle` | Title when a push arrives without one. |
| `defaultUrl` | Link when a push arrives without one (default `/`). |
| `icon`, `badge` | Fallback image URLs; the server normally sends them. |

To handle events yourself, import `showFromPush(event, options)` and `openFromClick(event)`
instead and call them from your own `push` and `notificationclick` listeners.

Links only ever open on your own site's origin. A link to another site opens your home page.

## Django template projects

`{% kvn_notify_scripts %}` loads the same client and creates it for you as `window.kvnNotify`:

| | |
| --- | --- |
| `window.kvnNotify.subscribe()`, `unsubscribe()`, `sendTest()` | Shortcuts |
| `window.kvnNotify.client` | The full client |
| `window.kvnNotify.createClient` | To create another one |

Buttons with `data-kvn-notify-button` are wired up automatically, and two events are sent on
`document`: `kvn-notify:change` (`detail: {permission, subscribed}`) and `kvn-notify:error`
(`detail`: the error).

In a classic service worker, `importScripts("/static/kvn_notify/sw.js")` adds the handlers. Set
`self.KVN_NOTIFY_SW_OPTIONS = {...}` before it to pass options, or
`self.KVN_NOTIFY_SW_MANUAL = true` to add them yourself through `self.kvnNotifySw`.
