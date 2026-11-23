// Small display helpers for the inbox list (pure functions, unit tested).

/**
 * Date for one list row, like a mail client: a time for today ("2:05 PM"),
 * month and day for earlier this year ("Nov 21"), plus the year for older mail.
 * `locale` is only passed by tests; the app uses the browser's own language.
 */
export function listDate(iso: string, now: Date = new Date(), locale?: string): string {
  const date = new Date(iso)
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' })
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' })
  }
  return date.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' })
}

const SNIPPET_LENGTH = 140

/** The body on one line, cut with "…" (CSS `truncate` then fits it to the row). */
export function snippet(body: string, max: number = SNIPPET_LENGTH): string {
  const oneLine = body.replace(/\s+/g, ' ').trim()
  return oneLine.length <= max ? oneLine : `${oneLine.slice(0, max - 1).trimEnd()}…`
}
