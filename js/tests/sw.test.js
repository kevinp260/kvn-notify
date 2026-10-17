import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { openFromClick, showFromPush, targetUrl } from "../src/sw.js";

const ORIGIN = "https://app.example.com";

let shown;
let opened;
let windows;

beforeEach(() => {
  shown = [];
  opened = [];
  windows = [];
  globalThis.self = {
    location: { origin: ORIGIN },
    registration: { showNotification: async (title, options) => shown.push({ title, options }) },
    clients: {
      matchAll: async () => windows,
      openWindow: async (url) => opened.push(url),
    },
  };
});

const pushEvent = (payload) => ({
  data: {
    json: () => (typeof payload === "string" ? JSON.parse(payload) : payload),
    text: () => String(payload),
  },
});

test("shows the title, body, icons and tag the server sent", async () => {
  await showFromPush(
    pushEvent({ v: 1, id: "n1", title: "[DOWN] Shop", body: "Timeout", url: "/m/4", tag: "incident-9",
      icon: "/i.png", badge: "/b.png", inbox: true, type: "monitor.down" }),
  );
  assert.equal(shown[0].title, "[DOWN] Shop");
  assert.equal(shown[0].options.body, "Timeout");
  assert.equal(shown[0].options.badge, "/b.png");
  assert.equal(shown[0].options.tag, "incident-9");
  assert.deepEqual(shown[0].options.data, { url: "/m/4", id: "n1", inbox: true, type: "monitor.down" });
});

test("a push that is not JSON still shows something", async () => {
  await showFromPush(pushEvent("plain words"), { defaultTitle: "My app" });
  assert.equal(shown[0].title, "My app");
  assert.equal(shown[0].options.body, "plain words");
});

test("links only open on the site's own origin", () => {
  assert.equal(targetUrl({ url: "/orders/1" }, ORIGIN), `${ORIGIN}/orders/1`);
  assert.equal(targetUrl({ url: "https://evil.example.net/x" }, ORIGIN), `${ORIGIN}/`);
  assert.equal(targetUrl({ url: "javascript:alert(1)" }, ORIGIN), `${ORIGIN}/`);
  assert.equal(targetUrl(null, ORIGIN), `${ORIGIN}/`);
});

test("inbox notifications carry their id so the page can mark them read", () => {
  assert.equal(targetUrl({ url: "/g/1?tab=a", id: "n1", inbox: true }, ORIGIN), `${ORIGIN}/g/1?tab=a&kvnNotificationId=n1`);
});

test("a click opens a new window when none is open", async () => {
  let closed = false;
  await openFromClick({ notification: { close: () => (closed = true), data: { url: "/x" } } });
  assert.ok(closed);
  assert.deepEqual(opened, [`${ORIGIN}/x`]);
});

test("a click reuses an open window", async () => {
  const calls = [];
  windows = [{ url: `${ORIGIN}/home`, navigate: async (u) => calls.push(["navigate", u]), focus: async () => calls.push(["focus"]) }];
  await openFromClick({ notification: { close() {}, data: { url: "/x" } } });
  assert.deepEqual(calls, [["navigate", `${ORIGIN}/x`], ["focus"]]);
  assert.deepEqual(opened, []);
});
