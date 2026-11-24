// A small wrapper around the browser Notification API (story 3.7).
// Desktop notifications are optional: the in-page toast always appears.
// Browsers only allow them on secure pages; http://localhost counts as secure.

export type AlertPermission = NotificationPermission | 'unsupported'

export function notificationsSupported(): boolean {
  return typeof window !== 'undefined' && typeof window.Notification !== 'undefined'
}

export function permission(): AlertPermission {
  return notificationsSupported() ? window.Notification.permission : 'unsupported'
}

/** Ask the user once. Only call this from a click: asking on page load is bad practice. */
export async function requestPermission(): Promise<AlertPermission> {
  if (!notificationsSupported()) return 'unsupported'
  return window.Notification.requestPermission()
}

/**
 * Show a system notification, but only when allowed AND the page is in the
 * background (Page Visibility API): while you look at the app, the toast is
 * enough. Clicking the notification calls `onClick`.
 */
export function notify(title: string, body: string, onClick: () => void): void {
  if (permission() !== 'granted' || document.visibilityState === 'visible') return
  const notification = new window.Notification(title, { body })
  notification.onclick = () => {
    window.focus() // bring the app's tab to the front
    onClick()
  }
}
