import type { Email } from '../api'
import { COLUMNS } from './columns'
import { EmailRow } from './EmailRow'

interface Props {
  emails: Email[]
  loading: boolean
  emptyText: string // differs per view
  selectedId: number | null
  onSelect: (id: number) => void
  /** Only in the Trash view: shows the "Empty trash" bar */
  onEmptyTrash?: () => void
}

/** The rows in the order the API returns them (the server sorts; we never re-sort). */
export function EmailList({ emails, loading, emptyText, selectedId, onSelect, onEmptyTrash }: Props) {
  if (loading) {
    return <p className="p-6 text-sm text-gray-500">Loading emails…</p>
  }
  if (emails.length === 0) {
    return (
      <p className="m-6 rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
        {emptyText}
      </p>
    )
  }
  return (
    <>
      {onEmptyTrash && (
        <div className="flex items-center justify-between gap-3 border-b border-gray-200 bg-white px-3 py-2 text-sm text-gray-600">
          <span>Emails in the Trash can be restored until you empty it.</span>
          <button
            type="button"
            onClick={onEmptyTrash}
            className="rounded-md border border-red-300 px-3 py-1 text-sm font-semibold text-red-700 hover:bg-red-50"
          >
            Empty trash
          </button>
        </div>
      )}
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
        <span className="text-right">Received</span>
      </div>
      <ul aria-label="Emails" className="divide-y divide-gray-100">
        {emails.map((email) => (
          // key: lets React track each row between renders
          <li key={email.id}>
            <EmailRow email={email} selected={email.id === selectedId} onSelect={onSelect} />
          </li>
        ))}
      </ul>
    </>
  )
}
