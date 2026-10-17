# kvn-notify-web

The browser half of [kvn-notify](https://github.com/kevinp260/kvn-notify): push notifications and
emails for Django. No dependencies and no framework, so it works with React, Vue, Svelte, Angular
or plain JavaScript.

```bash
npm install kvn-notify-web
```

## Turn notifications on

```js
import { createClient } from "kvn-notify-web";

// Session login (cookie): the client sends Django's CSRF token for you.
const notify = createClient({ baseUrl: "/notify" });

// Token login (e.g. SimpleJWT):
// const notify = createClient({
//   baseUrl: "/api/notify",
//   getHeaders: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
// });

enableButton.onclick = () => notify.subscribe(); // must run from a click
logoutButton.onclick = async () => {
  await notify.unsubscribe(); // before logging out, so the next person on this device gets nothing of yours
  await logout();
};
```

## Show notifications in your service worker

```js
// sw.js (bundled by Vite, Workbox, etc.)
import { registerPushHandlers } from "kvn-notify-web/sw";

registerPushHandlers();
```

The service worker shows whatever the server sends and opens the link when tapped, only on your
own site's origin.

## Optional in-app list

```js
const { results, unread_count } = await notify.inbox.list({ unread: true });
await notify.inbox.markRead(results[0].id);
await notify.handleOpenedFromPush(); // on page load: marks the tapped notification as read
```

Full documentation: <https://kevinp260.github.io/kvn-notify/>

MIT licence.
