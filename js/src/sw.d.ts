export interface PushHandlerOptions {
  /** Title when a push arrives without one. */
  defaultTitle?: string;
  /** Link when a push arrives without one. Default "/". */
  defaultUrl?: string;
  /** Fallback icon and badge URLs; the server normally sends them. */
  icon?: string;
  badge?: string;
}

export interface NotificationData {
  url?: string;
  id?: string | null;
  inbox?: boolean;
  type?: string | null;
}

export function showFromPush(event: PushEvent, options?: PushHandlerOptions): Promise<void>;
export function openFromClick(event: NotificationEvent): Promise<unknown>;
export function targetUrl(data: NotificationData | null | undefined, origin: string): string;
export function registerPushHandlers(options?: PushHandlerOptions): void;
