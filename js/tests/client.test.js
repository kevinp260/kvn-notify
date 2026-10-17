import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { createClient, KvnNotifyError, urlBase64ToUint8Array } from "../src/client.js";

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
