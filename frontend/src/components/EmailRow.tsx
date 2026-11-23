import type { Email } from '../api'
import { listDate, snippet } from '../format'
import { PRIORITIES } from '../priorities'
import { COLUMNS } from './columns'
import { PriorityBadge } from './PriorityBadge'

interface Props {
  email: Email
  selected: boolean
  onSelect: (id: number) => void
}

/**
 * One email on one line, like Gmail/Outlook: color bar, badge, sender,
 * subject + snippet, date - on the same grid columns as the list header
 * (columns.ts). The whole row is a <button>: click, or Tab + Enter, opens the
 * email in the reading pane; aria-current marks the open one.
 * New emails are bold; handled ones are greyed out (the API puts them last).
 */
export function EmailRow({ email, selected, onSelect }: Props) {
  const handled = email.status === 'handled'
  const accent = email.priority ? PRIORITIES[email.priority].color : '#D1D5DB'
  const strong = handled ? 'text-gray-600' : 'font-semibold text-gray-900'

  return (
    <button
      type="button"
      onClick={() => onSelect(email.id)}
      aria-current={selected ? 'true' : undefined}
      data-status={email.status}
      className={`flex w-full flex-wrap items-center gap-x-3 gap-y-1 border-l-4 px-3 py-2 text-left sm:grid ${COLUMNS} ${
        selected ? 'bg-blue-50' : 'hover:bg-gray-50'
      } ${handled ? 'opacity-60' : ''}`}
      style={{ borderLeftColor: accent }}
    >
      <span className="min-w-0 overflow-hidden">
        <PriorityBadge email={email} />
      </span>
      <span className={`w-36 min-w-0 truncate text-sm sm:w-auto ${strong}`}>{email.sender_name}</span>
      {/* On narrow screens subject + snippet get their own line */}
      <span className="order-last block min-w-0 basis-full truncate text-sm sm:order-none">
        <span data-testid="subject" className={strong}>
          {email.subject}
        </span>
        <span className="text-gray-500"> — {snippet(email.body)}</span>
      </span>
      <time dateTime={email.received_at} className="ml-auto text-right text-xs text-gray-500 sm:ml-0">
        {listDate(email.received_at)}
      </time>
    </button>
  )
}
