import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import {
  createBrowserSubscription,
  createClient,
  KvnNotifyError,
  needsInstall,
  removeBrowserSubscription,
  urlBase64ToUint8Array,
} from "../src/client.js";

let requests;
let responses;

beforeEach(() => {
  requests = [];
  responses = [];
  globalThis.document = { cookie: "other=1; csrftoken=tok123" };
  globalThis.fetch = async (url, init) => {
    requests.push({ url, ...init });
    const next = responses.shift() || { status: 200, body: {} };
    return {
      status: next.status,
      ok: next.status >= 200 && next.status < 300,
      json: async () => next.body,
    };
  };
});

test("session logins send the CSRF cookie on changes, not on reads", async () => {
  const notify = createClient({ baseUrl: "/api/notify/" });
  await notify.preferences.list();
  await notify.sendTest();
  assert.equal(requests[0].url, "/api/notify/preferences/");
  assert.equal(requests[0].headers["X-CSRFToken"], undefined);
  assert.equal(requests[1].method, "POST");
  assert.equal(requests[1].headers["X-CSRFToken"], "tok123");
  assert.equal(requests[1].credentials, "same-origin");
});

test("token logins send the Authorization header and no CSRF token", async () => {
  const notify = createClient({ getHeaders: async () => ({ Authorization: "Bearer abc" }) });
  await notify.inbox.markAllRead();
  assert.equal(requests[0].url, "/notify/inbox/read-all/");
  assert.equal(requests[0].headers.Authorization, "Bearer abc");
  assert.equal(requests[0].headers["X-CSRFToken"], undefined);
});

test("server errors become KvnNotifyError with the server's message", async () => {
  responses.push({ status: 409, body: { error: "No devices." } });
  const notify = createClient();
  await assert.rejects(notify.sendTest(), (error) => {
    assert.ok(error instanceof KvnNotifyError);
    assert.equal(error.status, 409);
    assert.equal(error.message, "No devices.");
    return true;
  });
});

test("inbox list builds its query", async () => {
  responses.push({ status: 200, body: { results: [] } });
  await createClient().inbox.list({ unread: true, page: 2, pageSize: 5 });
  assert.equal(requests[0].url, "/notify/inbox/?page=2&page_size=5&unread=1");
});

test("204 responses resolve to null", async () => {
  responses.push({ status: 204 });
  assert.equal(await createClient().inbox.markRead("abc"), null);
});

test("subscribe refuses cleanly where push is not supported", async () => {
  await assert.rejects(createClient().subscribe(), (error) => error.code === "unsupported");
});

test("VAPID keys decode from URL-safe base64", () => {
  assert.deepEqual([...urlBase64ToUint8Array("AQID_w")], [1, 2, 3, 255]);
});

test("a page with no service worker fails clearly instead of waiting forever", async () => {
  const saved = { window: globalThis.window, navigator: globalThis.navigator, Notification: globalThis.Notification };
  globalThis.window = { PushManager: {}, Notification: {} };
  Object.defineProperty(globalThis, "navigator", {
    value: { serviceWorker: { ready: new Promise(() => {}) } },
    configurable: true,
  });
  globalThis.Notification = { permission: "granted", requestPermission: async () => "granted" };
  try {
    const notify = createClient({ readyTimeout: 20 });
    assert.equal(await notify.isSubscribed(), false);
    await assert.rejects(notify.subscribe(), (error) => error.code === "no-service-worker");
  } finally {
    globalThis.window = saved.window;
    Object.defineProperty(globalThis, "navigator", { value: saved.navigator, configurable: true });
    globalThis.Notification = saved.Notification;
  }
});

test("an HttpOnly CSRF cookie falls back to the token in the page", async () => {
  globalThis.document = {
    cookie: "sessionid=abc",
    querySelector: (selector) => (selector.includes("csrfmiddlewaretoken") ? { value: "from-form" } : null),
  };
  await createClient().sendTest();
  assert.equal(requests[0].headers["X-CSRFToken"], "from-form");
});

test("a csrfToken option is used first", async () => {
  await createClient({ csrfToken: () => "given" }).sendTest();
  assert.equal(requests[0].headers["X-CSRFToken"], "given");
});

// A fake browser for the tests below: window, navigator and Notification, put back afterwards.
async function inBrowser({ userAgent = "Mozilla/5.0 (X11; Linux x86_64)", push = true, standalone = false, reg }, fn) {
  const saved = { window: globalThis.window, navigator: globalThis.navigator, Notification: globalThis.Notification };
  const calls = [];
  globalThis.window = {
    ...(push ? { PushManager: {}, Notification: {} } : {}),
    matchMedia: () => ({ matches: standalone }),
  };
  Object.defineProperty(globalThis, "navigator", {
    value: {
      userAgent,
      platform: "",
      maxTouchPoints: 0,
      ...(push ? { serviceWorker: { ready: Promise.resolve(reg) } } : {}),
    },
    configurable: true,
  });
  globalThis.Notification = {
    permission: "granted",
    requestPermission: async () => {
      calls.push("permission");
      return "granted";
    },
  };
  try {
    return await fn(calls);
  } finally {
    globalThis.window = saved.window;
    Object.defineProperty(globalThis, "navigator", { value: saved.navigator, configurable: true });
    globalThis.Notification = saved.Notification;
  }
}

function fakeRegistration(existing = null) {
  const subscription = {
    endpoint: "https://push.example.com/new",
    options: {},
    toJSON: () => ({ endpoint: "https://push.example.com/new", keys: { p256dh: "p", auth: "a" } }),
    unsubscribe: async () => true,
  };
  return {
    active: {},
    pushManager: {
      getSubscription: async () => existing,
      subscribe: async () => subscription,
    },
  };
}

test("an expired token is refreshed once and the request retried", async () => {
  let token = "old";
  let refreshes = 0;
  responses.push({ status: 401, body: {} }, { status: 202, body: { devices: 1 } });
  const notify = createClient({
    getHeaders: () => ({ Authorization: `Bearer ${token}` }),
    onUnauthorized: async () => {
      refreshes += 1;
      token = "new";
      return true;
    },
  });
  assert.deepEqual(await notify.sendTest(), { devices: 1 });
  assert.equal(refreshes, 1);
  assert.deepEqual(
    requests.map((r) => r.headers.Authorization),
    ["Bearer old", "Bearer new"],
  );
});

test("a refresh that fails, or a second 401, ends with the error", async () => {
  responses.push({ status: 401, body: {} });
  await assert.rejects(createClient({ onUnauthorized: () => false }).sendTest(), (e) => e.status === 401);
  assert.equal(requests.length, 1);

  requests = [];
  responses.push({ status: 401, body: {} }, { status: 401, body: {} });
  await assert.rejects(createClient({ onUnauthorized: () => true }).sendTest(), (e) => e.status === 401);
  assert.equal(requests.length, 2);
});

test("allauth's X-Session-Token and listed token headers skip the CSRF token", async () => {
  await createClient({ getHeaders: () => ({ "X-Session-Token": "s" }) }).sendTest();
  await createClient({ getHeaders: () => ({ "X-Api-Key": "k" }), tokenHeaders: ["X-Api-Key"] }).sendTest();
  await createClient({ getHeaders: () => ({ "X-Api-Key": "k" }) }).sendTest();
  assert.equal(requests[0].headers["X-CSRFToken"], undefined);
  assert.equal(requests[1].headers["X-CSRFToken"], undefined);
  assert.equal(requests[2].headers["X-CSRFToken"], "tok123"); // not a known token header
});

const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 Version/18.6 Mobile Safari/604.1";

test("needsInstall is true only in an iPhone browser tab without push", async () => {
  await inBrowser({ userAgent: IPHONE, push: false }, async () => {
    assert.equal(needsInstall(), true);
    await assert.rejects(createClient().subscribe(), (error) => error.code === "needs-install");
  });
  await inBrowser({ userAgent: IPHONE, push: true, standalone: true, reg: fakeRegistration() }, async () => {
    assert.equal(needsInstall(), false); // installed: push works
  });
  await inBrowser({ push: false }, async () => {
    assert.equal(needsInstall(), false); // a desktop browser without push just isn't supported
  });
});

test("subscribe asks permission before fetching the key", async () => {
  responses.push({ status: 200, body: { public_key: "AQID_w" } }, { status: 201, body: { id: 1 } });
  await inBrowser({ reg: fakeRegistration() }, async (calls) => {
    const realFetch = globalThis.fetch;
    globalThis.fetch = async (url, init) => {
      calls.push(url);
      return realFetch(url, init);
    };
    try {
      await createClient().subscribe();
    } finally {
      globalThis.fetch = realFetch;
    }
    assert.deepEqual(calls, ["permission", "/notify/vapid-key/", "/notify/subscriptions/"]);
  });
});

test("the browser-only helpers work without kvn-notify's endpoints", async () => {
  await inBrowser({ reg: fakeRegistration() }, async () => {
    const json = await createBrowserSubscription({ vapidPublicKey: "AQID_w" });
    assert.deepEqual(json, { endpoint: "https://push.example.com/new", keys: { p256dh: "p", auth: "a" } });
  });
  const existing = { endpoint: "https://push.example.com/old", unsubscribe: async () => true };
  await inBrowser({ reg: fakeRegistration(existing) }, async () => {
    assert.equal(await removeBrowserSubscription(), "https://push.example.com/old");
  });
  await inBrowser({ reg: fakeRegistration(null) }, async () => {
    assert.equal(await removeBrowserSubscription(), null);
  });
  assert.equal(requests.length, 0); // no request to any kvn-notify endpoint
});

test("the device list marks this browser's own device", async () => {
  const { createHash } = await import("node:crypto");
  const hash = (text) => createHash("sha256").update(text).digest("hex");
  let unsubscribed = 0;
  const mine = { endpoint: "https://push.example.com/mine", options: {}, unsubscribe: async () => (unsubscribed += 1) };
  const reg = { active: {}, pushManager: { getSubscription: async () => mine } };
  responses.push({
    status: 200,
    body: {
      results: [
        { id: 2, name: "Chrome on Android", endpoint_hash: hash("https://push.example.com/phone") },
        { id: 1, name: "Firefox on Linux", endpoint_hash: hash(mine.endpoint) },
      ],
    },
  });

  await inBrowser({ reg }, async () => {
    const notify = createClient();
    const { results } = await notify.devices.list();
    assert.deepEqual(results.map((d) => [d.id, d.current]), [[2, false], [1, true]]);

    // Another device: only the server row goes.
    await notify.devices.remove(results[0]);
    assert.equal(requests.at(-1).url, "/notify/subscriptions/2/");
    assert.equal(requests.at(-1).method, "DELETE");
    assert.equal(unsubscribed, 0);

    // This browser: the server row and the browser's own subscription.
    await notify.devices.remove(results[1]);
    assert.equal(requests.at(-1).url, "/notify/subscriptions/1/");
    assert.equal(unsubscribed, 1);
  });
});

test("the device list works where push is unavailable, with nothing marked current", async () => {
  responses.push({ status: 200, body: { results: [{ id: 3, endpoint_hash: "abc" }] } });
  const { results } = await createClient().devices.list();
  assert.equal(results[0].current, false);
  await createClient().devices.remove(3);
  assert.equal(requests.at(-1).url, "/notify/subscriptions/3/");
});
