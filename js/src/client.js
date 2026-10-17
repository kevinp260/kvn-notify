// kvn-notify-web: the browser half of kvn-notify. No dependencies, no framework.
//
//   import { createClient } from "kvn-notify-web";
//   const notify = createClient({ baseUrl: "/notify" });
//   button.onclick = () => notify.subscribe();

export class KvnNotifyError extends Error {
  constructor(message, { status = 0, code = "error" } = {}) {
    super(message);
    this.name = "KvnNotifyError";
    this.status = status;
    this.code = code;
  }
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const OPENED_PARAM = "kvnNotificationId";

export function isSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function urlBase64ToUint8Array(base64String) {
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
 * @param {string} [options.serviceWorker] URL of a service worker to register, if the app has none of its own.
 * @param {number} [options.readyTimeout=10000] Milliseconds to wait for a service worker before failing.
 */
export function createClient(options = {}) {
  const {
    baseUrl = "/notify",
    credentials = "same-origin",
    getHeaders,
    csrfCookieName = "csrftoken",
    serviceWorker,
    readyTimeout = 10000,
  } = options;
  const base = baseUrl.replace(/\/+$/, "");

  async function request(path, { method = "GET", body } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (getHeaders) Object.assign(headers, await getHeaders());
    const hasAuthorization = Object.keys(headers).some((h) => h.toLowerCase() === "authorization");
    if (UNSAFE_METHODS.has(method) && !hasAuthorization) {
      const token = readCookie(csrfCookieName);
      if (token) headers["X-CSRFToken"] = token;
    }
    const response = await fetch(`${base}${path}`, {
      method,
      headers,
      credentials,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (response.status === 204) return null;
    let data = null;
    try {
      data = await response.json();
    } catch (_error) {
      data = null;
    }
    if (!response.ok) {
      const message = (data && data.error) || `Request failed with status ${response.status}`;
      throw new KvnNotifyError(message, { status: response.status, code: "http" });
    }
    return data;
  }

  async function registration() {
    if (!isSupported()) {
      throw new KvnNotifyError("This browser does not support push notifications.", { code: "unsupported" });
    }
    if (serviceWorker) {
      return waitForActive(await navigator.serviceWorker.register(serviceWorker), readyTimeout);
    }
    // `ready` never settles when no service worker covers this page, so give up
    // with a clear message instead of leaving the button waiting forever.
    return withTimeout(navigator.serviceWorker.ready, readyTimeout, NO_WORKER_MESSAGE);
  }

  async function currentSubscription() {
    if (!isSupported()) return null;
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
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new KvnNotifyError("Notification permission was not granted.", { code: "permission-denied" });
      }
      const { public_key: publicKey } = await request("/vapid-key/");
      const keyBytes = urlBase64ToUint8Array(publicKey);
      let subscription = await reg.pushManager.getSubscription();
      if (subscription && !sameKey(subscription, keyBytes)) {
        await subscription.unsubscribe();
        subscription = null;
      }
      if (!subscription) {
        subscription = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
      }
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
