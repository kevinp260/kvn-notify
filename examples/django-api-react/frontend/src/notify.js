// --8<-- [start:client]
import { createClient } from "kvn-notify-web";

import { getAccessToken } from "./auth.js";

export const notify = createClient({
  baseUrl: "/api/notify",
  getHeaders: () => ({ Authorization: `Bearer ${getAccessToken()}` }),
});
// --8<-- [end:client]

// --8<-- [start:register]
export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  // In development Vite serves the source as a module; the build writes a plain /sw.js.
  if (import.meta.env.DEV) navigator.serviceWorker.register("/src/sw.js", { type: "module", scope: "/" });
  else navigator.serviceWorker.register("/sw.js");
}
// --8<-- [end:register]
