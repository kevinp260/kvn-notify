export class KvnNotifyError extends Error {
  /** HTTP status for server errors, 0 otherwise. */
  status: number;
  /** "http", "unsupported", "needs-install", "permission-denied", "no-service-worker" or "error". */
  code: string;
}

export interface ClientOptions {
  /** Where kvn_notify.urls is included. Default "/notify". */
  baseUrl?: string;
  /** "include" for a cookie session on another origin. Default "same-origin". */
  credentials?: RequestCredentials;
  /** Extra headers per request, e.g. async () => ({ Authorization: `Bearer ${token}` }). */
  getHeaders?: () => Record<string, string> | Promise<Record<string, string>>;
  /** Django's CSRF cookie name, sent as X-CSRFToken for session logins. Default "csrftoken". */
  csrfCookieName?: string;
  /** The CSRF token, for when the cookie is HttpOnly and the page has no token to read. */
  csrfToken?: string | (() => string);
  /** URL of a service worker to register, for apps without one of their own. */
  serviceWorker?: string;
  /** Milliseconds to wait for a service worker before failing with code "no-service-worker". Default 10000. */
  readyTimeout?: number;
  /** Headers from getHeaders that carry a login token; requests with one get no CSRF token.
   * Default ["Authorization", "X-Session-Token"]. Match the server's KVN_NOTIFY["TOKEN_HEADERS"]. */
  tokenHeaders?: string[];
  /** Called when a request gets 401, e.g. to refresh an expired token. Return true to retry once. */
  onUnauthorized?: () => boolean | Promise<boolean>;
}

export interface BrowserSubscriptionJSON {
  endpoint: string;
  expirationTime?: number | null;
  keys: { p256dh: string; auth: string };
}

export interface InboxItem {
  id: string;
  type: string;
  title: string;
  body: string;
  url: string;
  data: Record<string, unknown>;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface InboxPage {
  results: InboxItem[];
  count: number;
  page: number;
  next_page: number | null;
  unread_count: number;
}

export interface Device {
  id: number;
  /** e.g. "Chrome on Android", or the name given when subscribing. */
  name: string;
  /** False once the push service has rejected it for good. */
  active: boolean;
  /** SHA-256 of the push address; the address itself is never returned. */
  endpoint_hash: string;
  created_at: string;
  last_success_at: string | null;
  /** True for the device this browser is subscribed with. */
  current: boolean;
}

export interface PreferenceRow {
  type: string;
  description: string;
  required: boolean;
  channels: Record<string, boolean>;
}

export interface KvnNotifyClient {
  isSupported(): boolean;
  /** True on iPhone/iPad when the site must be added to the Home Screen before push works. */
  needsInstall(): boolean;
  permission(): NotificationPermission | "unsupported";
  isSubscribed(): Promise<boolean>;
  subscribe(): Promise<PushSubscription>;
  unsubscribe(): Promise<boolean>;
  sendTest(): Promise<{ devices: number }>;
  devices: {
    list(): Promise<{ results: Device[] }>;
    /** Removing this browser's own device also drops its subscription. */
    remove(device: Device | number): Promise<null>;
  };
  preferences: {
    list(): Promise<{ results: PreferenceRow[] }>;
    set(type: string, channel: string, enabled: boolean): Promise<{ results: PreferenceRow[] }>;
  };
  inbox: {
    list(options?: { unread?: boolean; page?: number; pageSize?: number }): Promise<InboxPage>;
    unreadCount(): Promise<number>;
    markRead(id: string): Promise<null>;
    markAllRead(): Promise<{ marked: number }>;
  };
  handleOpenedFromPush(): Promise<string | null>;
}

export function createClient(options?: ClientOptions): KvnNotifyClient;
export function isSupported(): boolean;
/** True on iPhone/iPad when the site must be added to the Home Screen before push works. */
export function needsInstall(): boolean;
/** Ask permission and subscribe this browser, without kvn-notify's endpoints. Returns the JSON to send to your server. */
export function createBrowserSubscription(options: {
  vapidPublicKey: string;
  serviceWorker?: string;
  readyTimeout?: number;
}): Promise<BrowserSubscriptionJSON>;
/** Unsubscribe this browser. Returns the endpoint it had, or null. */
export function removeBrowserSubscription(options?: { serviceWorker?: string; readyTimeout?: number }): Promise<string | null>;
export function urlBase64ToUint8Array(base64String: string): Uint8Array;
