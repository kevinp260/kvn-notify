/* kvn-notify-web 1.0.0 (browser script). Generated from js/src by js/scripts/build-static.mjs; do not edit. */
(function () {
"use strict";
// kvn-notify-web: the browser half of kvn-notify. No dependencies, no framework.
//
//   import { createClient } from "kvn-notify-web";
//   const notify = createClient({ baseUrl: "/notify" });
//   button.onclick = () => notify.subscribe();

class KvnNotifyError extends Error {
  constructor(message, { status = 0, code = "error" } = {}) {
    super(message);
    this.name = "KvnNotifyError";
    this.status = status;
    this.code = code;
  }
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const OPENED_PARAM = "kvnNotificationId";
// Same default as the server's KVN_NOTIFY["TOKEN_HEADERS"]: requests carrying one of
// these log in with a token, so they need no CSRF token.
const DEFAULT_TOKEN_HEADERS = ["Authorization", "X-Session-Token"];

function isSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function isAppleMobile() {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  // iPadOS reports itself as a Mac; touch support gives it away.
  return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isInstalledApp() {
  if (typeof window === "undefined") return false;
  const standalone = window.matchMedia && window.matchMedia("(display-mode: standalone)").matches;
  return Boolean(standalone || navigator.standalone === true);
}

/**
 * True on an iPhone or iPad where push is only available once the site is added to
 * the Home Screen (iOS 16.4+). Show "Add to Home Screen" instead of the button then.
 */
function needsInstall() {
  return isAppleMobile() && !isInstalledApp() && !isSupported();
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

function readCookie(name) {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : "";
}

// With CSRF_COOKIE_HTTPONLY = True the page cannot read the cookie, so also look for
// the token Django put in the page: a <meta name="csrf-token"> or a form's hidden input.
function readPageToken() {
  if (typeof document === "undefined" || !document.querySelector) return "";
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return input && input.value ? input.value : "";
}

const NO_WORKER_MESSAGE =
  "No service worker controls this page. Register one whose scope covers the page " +
  "(see the kvn-notify docs), or pass `serviceWorker` to createClient().";

function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_resolve, reject) => {
    timer = setTimeout(() => reject(new KvnNotifyError(message, { code: "no-service-worker" })), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function waitForActive(reg, ms) {
  if (reg.active) return Promise.resolve(reg);
  const worker = reg.installing || reg.waiting;
  const activated = new Promise((resolve, reject) => {
    if (!worker) return reject(new KvnNotifyError(NO_WORKER_MESSAGE, { code: "no-service-worker" }));
    worker.addEventListener("statechange", () => {
      if (worker.state === "activated") resolve(reg);
      if (worker.state === "redundant") {
        reject(new KvnNotifyError("The service worker failed to install.", { code: "no-service-worker" }));
      }
    });
  });
  return withTimeout(activated, ms, NO_WORKER_MESSAGE);
}

async function getRegistration({ serviceWorker, readyTimeout = 10000 } = {}) {
  if (!isSupported()) {
    const message = needsInstall()
      ? "Add this site to the Home Screen first: iPhone and iPad only allow notifications for installed apps."
      : "This browser does not support push notifications.";
    throw new KvnNotifyError(message, { code: needsInstall() ? "needs-install" : "unsupported" });
  }
  if (serviceWorker) {
    return waitForActive(await navigator.serviceWorker.register(serviceWorker), readyTimeout);
  }
  // `ready` never settles when no service worker covers this page, so give up
  // with a clear message instead of leaving the button waiting forever.
  return withTimeout(navigator.serviceWorker.ready, readyTimeout, NO_WORKER_MESSAGE);
}

// Permission is asked first, straight after the click: Safari only shows the prompt
// while the click still counts as "recent", so the key is fetched afterwards.
async function subscribeBrowser(reg, publicKey) {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new KvnNotifyError("Notification permission was not granted.", { code: "permission-denied" });
  }
  const key = typeof publicKey === "function" ? await publicKey() : publicKey;
  const keyBytes = urlBase64ToUint8Array(key);
  let subscription = await reg.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, keyBytes)) {
    await subscription.unsubscribe();
    subscription = null;
  }
  if (!subscription) {
    subscription = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
  }
  return subscription;
}

/**
 * The browser half on its own, for apps with their own endpoints: ask permission
 * (call it from a click), subscribe this browser and return the subscription JSON
 * ({ endpoint, keys: { p256dh, auth } }) for your code to send to your server, which
 * can pass it to kvn_notify.register_device().
 *
 * @param {{ vapidPublicKey: string, serviceWorker?: string, readyTimeout?: number }} options
 */
async function createBrowserSubscription({ vapidPublicKey, serviceWorker, readyTimeout } = {}) {
  if (!vapidPublicKey) throw new KvnNotifyError("vapidPublicKey is required.", { code: "error" });
  const reg = await getRegistration({ serviceWorker, readyTimeout });
  return (await subscribeBrowser(reg, vapidPublicKey)).toJSON();
}

/**
 * Unsubscribe this browser. Returns the endpoint it had (send it to your server so it
 * can call kvn_notify.remove_device()), or null if it was not subscribed.
 */
async function removeBrowserSubscription({ serviceWorker, readyTimeout } = {}) {
  if (!isSupported()) return null;
  let reg;
  try {
    reg = await getRegistration({ serviceWorker, readyTimeout });
  } catch (error) {
    if (error instanceof KvnNotifyError && error.code === "no-service-worker") return null;
    throw error;
  }
  const subscription = await reg.pushManager.getSubscription();
  if (!subscription) return null;
  const { endpoint } = subscription;
  await subscription.unsubscribe();
  return endpoint;
}

// SHA-256 of a push address, as hex: how the server's device list names this browser
// without ever sending the address back.
async function sha256Hex(text) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function sameKey(subscription, keyBytes) {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return false;
  const a = new Uint8Array(current);
  if (a.length !== keyBytes.length) return false;
  return a.every((value, index) => value === keyBytes[index]);
}

/**
 * Create a client for the kvn-notify endpoints.
 *
 * @param {object} [options]
 * @param {string} [options.baseUrl="/notify"] Where kvn_notify.urls is included.
 * @param {RequestCredentials} [options.credentials="same-origin"] "include" for a cookie session on another origin.
 * @param {() => (Record<string,string>|Promise<Record<string,string>>)} [options.getHeaders]
 *   Extra headers per request, e.g. async () => ({ Authorization: `Bearer ${token}` }).
 * @param {string} [options.csrfCookieName="csrftoken"] Django's CSRF cookie, sent as X-CSRFToken for sessions.
 * @param {string | (() => (string|Promise<string>))} [options.csrfToken] The CSRF token itself, for when the
 *   cookie can't be read (HttpOnly, or set on the API's own host) and the page has no token. A function may
 *   be async, e.g. to fetch the token from your API once. Otherwise found automatically.
 * @param {string} [options.serviceWorker] URL of a service worker to register, if the app has none of its own.
 * @param {number} [options.readyTimeout=10000] Milliseconds to wait for a service worker before failing.
 * @param {string[]} [options.tokenHeaders=["Authorization","X-Session-Token"]] Headers from getHeaders that
 *   carry a login token; requests with one are sent without a CSRF token (match KVN_NOTIFY["TOKEN_HEADERS"]).
 * @param {() => (boolean|Promise<boolean>)} [options.onUnauthorized] Called when a request gets 401, e.g. to
 *   refresh an expired token. Return true and the request is retried once (getHeaders runs again).
 * @param {() => (boolean|Promise<boolean>)} [options.onCsrfFailure] Called when the server refused only the
 *   CSRF token (it changes when Django logs someone in), e.g. to drop a cached token. Return true and the
 *   request is retried once, reading csrfToken again.
 */
function createClient(options = {}) {
  const {
    baseUrl = "/notify",
    credentials = "same-origin",
    getHeaders,
    csrfCookieName = "csrftoken",
    csrfToken,
    serviceWorker,
    readyTimeout = 10000,
    tokenHeaders = DEFAULT_TOKEN_HEADERS,
    onUnauthorized,
    onCsrfFailure,
  } = options;
  const base = baseUrl.replace(/\/+$/, "");
  const tokenHeaderNames = new Set(tokenHeaders.map((h) => h.toLowerCase()));

  // `retried` holds the recoveries already tried for this call, so each runs at most once.
  async function request(path, { method = "GET", body } = {}, retried = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (getHeaders) Object.assign(headers, await getHeaders());
    const hasToken = Object.entries(headers).some(([h, v]) => v && tokenHeaderNames.has(h.toLowerCase()));
    if (UNSAFE_METHODS.has(method) && !hasToken) {
      const given = typeof csrfToken === "function" ? await csrfToken() : csrfToken;
      const token = given || readCookie(csrfCookieName) || readPageToken();
      if (token) headers["X-CSRFToken"] = token;
    }
    const response = await fetch(`${base}${path}`, {
      method,
      headers,
      credentials,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 401 && onUnauthorized && !retried.unauthorized && (await onUnauthorized())) {
      return request(path, { method, body }, { ...retried, unauthorized: true });
    }
    if (response.status === 204) return null;
    let data = null;
    try {
      data = await response.json();
    } catch (_error) {
      data = null;
    }
    const csrfRefused = response.status === 403 && data !== null && data.code === "csrf_failed";
    if (csrfRefused && onCsrfFailure && !retried.csrf && (await onCsrfFailure())) {
      return request(path, { method, body }, { ...retried, csrf: true });
    }
    if (!response.ok) {
      const message = (data && data.error) || `Request failed with status ${response.status}`;
      throw new KvnNotifyError(message, { status: response.status, code: csrfRefused ? "csrf" : "http" });
    }
    return data;
  }

  function registration() {
    return getRegistration({ serviceWorker, readyTimeout });
  }

  async function currentSubscription() {
    // Never allowed means never subscribed: answer at once rather than wait for a worker.
    if (!isSupported() || Notification.permission !== "granted") return null;
    let reg;
    try {
      reg = await registration();
    } catch (error) {
      if (error instanceof KvnNotifyError && error.code === "no-service-worker") return null;
      throw error;
    }
    return reg.pushManager.getSubscription();
  }

  return {
    isSupported,
    needsInstall,

    /** "granted", "denied", "default", or "unsupported". */
    permission() {
      return isSupported() ? Notification.permission : "unsupported";
    },

    async isSubscribed() {
      if (!isSupported() || Notification.permission !== "granted") return false;
      return (await currentSubscription()) !== null;
    },

    /** Ask permission (call it from a click), subscribe this device and save it on the server. */
    async subscribe() {
      const reg = await registration();
      const subscription = await subscribeBrowser(reg, async () => (await request("/vapid-key/")).public_key);
      await request("/subscriptions/", { method: "POST", body: subscription.toJSON() });
      return subscription;
    },

    /** Remove this device. Call it before logging out. */
    async unsubscribe() {
      const subscription = await currentSubscription();
      if (!subscription) return false;
      try {
        await request("/subscriptions/", { method: "DELETE", body: { endpoint: subscription.endpoint } });
      } finally {
        await subscription.unsubscribe();
      }
      return true;
    },

    devices: {
      /**
       * The user's devices, newest first, for a "your devices" list. The one this
       * browser is subscribed with has `current: true`.
       */
      async list() {
        const data = await request("/subscriptions/");
        const subscription = await currentSubscription();
        const here = subscription && globalThis.crypto?.subtle ? await sha256Hex(subscription.endpoint) : null;
        return { results: data.results.map((device) => ({ ...device, current: device.endpoint_hash === here })) };
      },

      /**
       * Remove a device (an entry from list(), or its id). Removing this browser's
       * own device also drops its subscription, as unsubscribe() does.
       */
      async remove(device) {
        const id = typeof device === "object" && device !== null ? device.id : device;
        await request(`/subscriptions/${encodeURIComponent(id)}/`, { method: "DELETE" });
        if (typeof device === "object" && device !== null && device.current) {
          const subscription = await currentSubscription();
          if (subscription) await subscription.unsubscribe();
        }
        return null;
      },
    },

    /** Send a test notification to this user's devices. */
    sendTest() {
      return request("/test/", { method: "POST", body: {} });
    },

    preferences: {
      list: () => request("/preferences/"),
      set: (type, channel, enabled) =>
        request("/preferences/", { method: "POST", body: { type, channel, enabled } }),
    },

    inbox: {
      list({ unread = false, page = 1, pageSize = 20 } = {}) {
        const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
        if (unread) query.set("unread", "1");
        return request(`/inbox/?${query}`);
      },
      async unreadCount() {
        return (await request("/inbox/unread-count/")).unread_count;
      },
      markRead: (id) => request(`/inbox/${encodeURIComponent(id)}/read/`, { method: "POST", body: {} }),
      markAllRead: () => request("/inbox/read-all/", { method: "POST", body: {} }),
    },

    /**
     * Call once on page load when the inbox is used: if the page was opened by
     * tapping a push, mark that notification read and tidy the URL. Returns its id.
     */
    async handleOpenedFromPush() {
      if (typeof window === "undefined") return null;
      const url = new URL(window.location.href);
      const id = url.searchParams.get(OPENED_PARAM);
      if (!id) return null;
      url.searchParams.delete(OPENED_PARAM);
      window.history.replaceState(window.history.state, "", url.toString());
      try {
        await request(`/inbox/${encodeURIComponent(id)}/read/`, { method: "POST", body: {} });
      } catch (_error) {
        // Not in the inbox, or already read: nothing to do.
      }
      return id;
    },
  };
}

function bindButtons(client) {
  const buttons = document.querySelectorAll("[data-kvn-notify-button]");
  if (!buttons.length) return;
  async function refresh() {
    const permission = client.permission();
    const subscribed = await client.isSubscribed().catch(() => false);
    buttons.forEach((button) => {
      const d = button.dataset;
      if (needsInstall()) {
        button.disabled = true;
        button.textContent = d.labelInstall || "Add this site to your Home Screen to turn on notifications";
      } else if (permission === "unsupported") {
        button.disabled = true;
        button.textContent = d.labelUnsupported || "Notifications are not supported in this browser";
      } else if (permission === "denied") {
        button.disabled = true;
        button.textContent = d.labelBlocked || "Notifications are blocked in your browser settings";
      } else {
        button.disabled = false;
        button.textContent = subscribed ? d.labelOn || "Turn off notifications" : d.labelOff || "Turn on notifications";
      }
      button.setAttribute("aria-pressed", subscribed ? "true" : "false");
    });
    document.dispatchEvent(new CustomEvent("kvn-notify:change", { detail: { permission, subscribed } }));
  }
  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        if (await client.isSubscribed()) await client.unsubscribe();
        else await client.subscribe();
      } catch (error) {
        document.dispatchEvent(new CustomEvent("kvn-notify:error", { detail: error }));
      }
      await refresh();
    });
  });
  refresh();
}

const script = document.currentScript;
const config = (script && script.dataset) || {};
const client = createClient({
  baseUrl: config.baseUrl || "/notify",
  serviceWorker: config.serviceWorker || undefined,
  csrfCookieName: config.csrfCookieName || "csrftoken",
  csrfToken: config.csrfToken || undefined,
});
window.kvnNotify = {
  createClient,
  isSupported,
  needsInstall,
  createBrowserSubscription,
  removeBrowserSubscription,
  urlBase64ToUint8Array,
  KvnNotifyError,
  client,
};
window.kvnNotify.subscribe = () => client.subscribe();
window.kvnNotify.unsubscribe = () => client.unsubscribe();
window.kvnNotify.sendTest = () => client.sendTest();
function start() {
  bindButtons(client);
  if (config.inbox === "true") client.handleOpenedFromPush();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();
})();
