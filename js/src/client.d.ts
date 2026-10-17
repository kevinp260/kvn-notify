export class KvnNotifyError extends Error {
  /** HTTP status for server errors, 0 otherwise. */
  status: number;
  /** "http", "unsupported", "permission-denied", "no-service-worker" or "error". */
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
  /** URL of a service worker to register, for apps without one of their own. */
  serviceWorker?: string;
  /** Milliseconds to wait for a service worker before failing with code "no-service-worker". Default 10000. */
  readyTimeout?: number;
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

export interface PreferenceRow {
  type: string;
  description: string;
  required: boolean;
  channels: Record<string, boolean>;
}

export interface KvnNotifyClient {
  isSupported(): boolean;
  permission(): NotificationPermission | "unsupported";
  isSubscribed(): Promise<boolean>;
  subscribe(): Promise<PushSubscription>;
  unsubscribe(): Promise<boolean>;
  sendTest(): Promise<{ devices: number }>;
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
export function urlBase64ToUint8Array(base64String: string): Uint8Array;
