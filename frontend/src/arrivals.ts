// New-mail detection (story 3b.5). Emails arrive from the separate Email
// Generator through the inbox's ingest API, so the page has to notice them
// itself: it polls GET /api/emails/summary and compares the counts.
import type { EmailSummary } from './api'

/** How often the inbox asks "anything new?" (one small query, no AI). */
export const POLL_INTERVAL_MS = 15_000

/** Every email the inbox holds: active ones plus the Trash. */
function total(summary: EmailSummary): number {
  return summary.all + summary.trash
}

/**
 * How many emails arrived between two summaries.
 *
 * `all` alone would be wrong: a delete lowers it and an Undo raises it again,
 * which would look like "1 new email". `all + trash` stays the same on delete
 * and restore and only drops when the Trash is emptied. Nothing the user does
 * in the inbox raises it, so any increase is mail that arrived.
 * Known limit: emptying the Trash and receiving mail within one poll interval
 * cancel out partly (the message shows fewer; the list is still right).
 */
export function arrived(previous: EmailSummary | null, next: EmailSummary): number {
  if (previous === null) return 0 // first load: nothing to compare with
  return Math.max(0, total(next) - total(previous))
}

export function arrivalMessage(count: number): string {
  return `${count} new email${count === 1 ? '' : 's'} arrived`
}
