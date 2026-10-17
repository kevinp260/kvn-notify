// Builds the plain-script copies of the client and service worker that ship inside
// the Python package, for Django template projects with no JavaScript build step.
//
//   node scripts/build-static.mjs
//
// Output: src/kvn_notify/static/kvn_notify/{kvn-notify.js,sw.js} (repo root relative).

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..", "..");
const outDir = resolve(root, "src", "kvn_notify", "static", "kvn_notify");
const version = JSON.parse(readFileSync(resolve(here, "..", "package.json"), "utf8")).version;

function stripExports(source) {
  return source.replace(/^export (?=(async )?function |class |const )/gm, "");
}

const banner = (name) =>
  `/* kvn-notify-web ${version} (${name}). Generated from js/src by js/scripts/build-static.mjs; do not edit. */\n`;

const client = stripExports(readFileSync(resolve(here, "..", "src", "client.js"), "utf8"));
const clientBundle = `${banner("browser script")}(function () {
"use strict";
${client}
function bindButtons(client) {
  const buttons = document.querySelectorAll("[data-kvn-notify-button]");
  if (!buttons.length) return;
  async function refresh() {
    const permission = client.permission();
    const subscribed = await client.isSubscribed().catch(() => false);
    buttons.forEach((button) => {
      const d = button.dataset;
      if (permission === "unsupported") {
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
});
window.kvnNotify = { createClient, isSupported, urlBase64ToUint8Array, KvnNotifyError, client };
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
`;

const sw = stripExports(readFileSync(resolve(here, "..", "src", "sw.js"), "utf8"));
const swBundle = `${banner("service worker script")}// In your own service worker: importScripts("/static/kvn_notify/sw.js");
// Options can be set first: self.KVN_NOTIFY_SW_OPTIONS = { defaultTitle: "My app" };
(function () {
"use strict";
${sw}
self.kvnNotifySw = { showFromPush, openFromClick, targetUrl, registerPushHandlers };
if (!self.KVN_NOTIFY_SW_MANUAL) registerPushHandlers(self.KVN_NOTIFY_SW_OPTIONS || {});
})();
`;

writeFileSync(resolve(outDir, "kvn-notify.js"), clientBundle);
writeFileSync(resolve(outDir, "sw.js"), swBundle);
console.log(`Wrote ${resolve(outDir, "kvn-notify.js")} and ${resolve(outDir, "sw.js")}`);
