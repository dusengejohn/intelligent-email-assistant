import type { Email, Priority } from '../api'
import { COLUMNS } from './columns'
import { EmailRow } from './EmailRow'

interface Props {
  emails: Email[]
  loading: boolean
  savingId: number | null
  onPriorityChange: (id: number, priority: Priority) => void
}

/** The rows in the order the API returns them (the server sorts; we never re-sort). */
export function EmailList({ emails, loading, savingId, onPriorityChange }: Props) {
  if (loading) {
    return <p className="p-6 text-sm text-gray-500">Loading emails…</p>
  }
  if (emails.length === 0) {
    return (
      <p className="m-6 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
        No emails yet. Click Generate to create some.
      </p>
    )
  }
  return (
    <>
      {/* Column header: sticks to the top of the scroll area while the list scrolls
          under it. Visual only (aria-hidden): each row already reads as one email. */}
      <div
        data-testid="list-header"
        aria-hidden="true"
        className={`sticky top-0 z-10 hidden items-center gap-x-3 border-b border-l-4 border-gray-200 border-l-transparent bg-gray-50 px-3 py-1.5 text-xs font-semibold tracking-wide text-gray-500 uppercase sm:grid ${COLUMNS}`}
      >
        <span>Priority</span>
        <span>From</span>
        <span>Subject</span>
        <span>Change</span>
        <span className="text-right">Received</span>
      </div>
      <ul aria-label="Emails" className="divide-y divide-gray-100">
        {emails.map((email) => (
          // key: lets React track each row between renders
          <li key={email.id}>
            <EmailRow
              email={email}
              saving={savingId === email.id}
              onPriorityChange={onPriorityChange}
            />
          </li>
        ))}
      </ul>
    </>
  )
}
