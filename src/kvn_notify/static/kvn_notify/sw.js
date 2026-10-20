/* kvn-notify-web 1.0.0 (service worker script). Generated from js/src by js/scripts/build-static.mjs; do not edit. */
// In your own service worker: importScripts("/static/kvn_notify/sw.js");
// Options can be set first: self.KVN_NOTIFY_SW_OPTIONS = { defaultTitle: "My app" };
(function () {
"use strict";
// Service worker half of kvn-notify-web. It holds no app logic: it shows what the
// server sends (see docs/payload.md) and opens the link when the notification is tapped.
//
//   import { registerPushHandlers } from "kvn-notify-web/sw";
//   registerPushHandlers();

const OPENED_PARAM = "kvnNotificationId";

function parsePayload(event) {
  if (!event.data) return {};
  try {
    return event.data.json();
  } catch (_error) {
    return { body: event.data.text() };
  }
}

/** Show the notification for one push event. Returns the showNotification promise. */
function showFromPush(event, options = {}) {
  const payload = parsePayload(event);
  const title = payload.title || options.defaultTitle || "New notification";
  return self.registration.showNotification(title, {
    body: payload.body || "",
    icon: payload.icon || options.icon || undefined,
    badge: payload.badge || options.badge || undefined,
    tag: payload.tag || payload.id || undefined,
    renotify: false,
    data: {
      url: payload.url || options.defaultUrl || "/",
      id: payload.id || null,
      inbox: Boolean(payload.inbox),
      type: payload.type || null,
    },
  });
}

/** Resolve the link to open, only ever on this site's own origin. */
function targetUrl(data, origin) {
  let url;
  try {
    url = new URL((data && data.url) || "/", origin);
  } catch (_error) {
    url = new URL("/", origin);
  }
  if (url.origin !== origin) url = new URL("/", origin);
  if (data && data.inbox && data.id) url.searchParams.set(OPENED_PARAM, data.id);
  return url.href;
}

/** Focus an open window of the app on the link, or open a new one. */
async function openFromClick(event) {
  event.notification.close();
  const destination = targetUrl(event.notification.data, self.location.origin);
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const exact = windows.find((client) => client.url === destination);
  if (exact && "focus" in exact) return exact.focus();
  for (const client of windows) {
    if ("navigate" in client && "focus" in client) {
      await client.navigate(destination);
      return client.focus();
    }
  }
  return self.clients.openWindow(destination);
}

/** Add the push and notificationclick listeners to this service worker. */
function registerPushHandlers(options = {}) {
  self.addEventListener("push", (event) => {
    event.waitUntil(showFromPush(event, options));
  });
  self.addEventListener("notificationclick", (event) => {
    event.waitUntil(openFromClick(event));
  });
}

self.kvnNotifySw = { showFromPush, openFromClick, targetUrl, registerPushHandlers };
if (!self.KVN_NOTIFY_SW_MANUAL) registerPushHandlers(self.KVN_NOTIFY_SW_OPTIONS || {});
})();
