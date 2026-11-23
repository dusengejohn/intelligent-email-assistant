import type { Email, Priority } from '../api'
import { listDate, snippet } from '../format'
import { PRIORITIES } from '../priorities'
import { COLUMNS } from './columns'
import { PriorityBadge } from './PriorityBadge'
import { PriorityPicker } from './PriorityPicker'

interface Props {
  email: Email
  saving: boolean
  onPriorityChange: (id: number, priority: Priority) => void
}

/**
 * One email on one line, like Gmail/Outlook: color bar, badge, sender,
 * subject + snippet, compact priority picker, date - on the same grid columns
 * as the list header (columns.ts), so everything lines up.
 * New emails are bold; handled ones are greyed out (the API puts them last).
 * The picker and the reason tooltip stay here until the reading pane (story 3.6).
 */
export function EmailRow({ email, saving, onPriorityChange }: Props) {
  const handled = email.status === 'handled'
  const accent = email.priority ? PRIORITIES[email.priority].color : '#D1D5DB'
  const strong = handled ? 'text-gray-600' : 'font-semibold text-gray-900'

  return (
    <div
      data-status={email.status}
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-l-4 px-3 py-2 hover:bg-gray-50 sm:grid ${COLUMNS} ${
        handled ? 'opacity-60' : ''
      }`}
      style={{ borderLeftColor: accent }}
    >
      <span className="min-w-0 overflow-hidden" title={email.priority_reason ?? undefined}>
        <PriorityBadge email={email} />
      </span>
      <span className={`w-36 min-w-0 truncate text-sm sm:w-auto ${strong}`}>
        {email.sender_name}
      </span>
      {/* On narrow screens subject + snippet get their own line */}
      <p className="order-last min-w-0 basis-full truncate text-sm sm:order-none">
        <span data-testid="subject" className={strong}>
          {email.subject}
        </span>
        <span className="text-gray-500"> — {snippet(email.body)}</span>
      </p>
      <span className="ml-auto sm:ml-0">
        <PriorityPicker
          value={email.priority}
          saving={saving}
          onChange={(priority) => onPriorityChange(email.id, priority)}
        />
      </span>
      <time dateTime={email.received_at} className="text-right text-xs text-gray-500">
        {listDate(email.received_at)}
      </time>
    </div>
  )
}
