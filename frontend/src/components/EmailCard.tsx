import type { Email, Priority } from '../api'
import { PRIORITIES } from '../priorities'
import { PriorityBadge } from './PriorityBadge'
import { PriorityPicker } from './PriorityPicker'

/** UTC ISO string from the API -> date and time in the browser's own timezone. */
function localDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

interface Props {
  email: Email
  saving: boolean
  onPriorityChange: (id: number, priority: Priority) => void
}

export function EmailCard({ email, saving, onPriorityChange }: Props) {
  // Thin left border in the priority color (grey when unclassified)
  const accent = email.priority ? PRIORITIES[email.priority].color : '#D1D5DB'
  return (
    <article
      className="rounded-lg border border-l-4 border-gray-200 bg-white p-4 shadow-sm"
      style={{ borderLeftColor: accent }}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <PriorityBadge email={email} />
        <div className="flex items-center gap-3">
          <PriorityPicker
            value={email.priority}
            saving={saving}
            onChange={(priority) => onPriorityChange(email.id, priority)}
          />
          <time dateTime={email.received_at} className="text-xs text-gray-500">
            {localDateTime(email.received_at)}
          </time>
        </div>
      </header>
      <p className="mt-2 text-sm">
        <span className="font-semibold text-gray-900">{email.sender_name}</span>{' '}
        <span className="text-gray-500">&lt;{email.sender_email}&gt;</span>
      </p>
      <h3 className="mt-1 font-medium text-gray-900">{email.subject}</h3>
      {email.priority_reason && (
        <p className="mt-1 text-sm text-gray-700 italic">{email.priority_reason}</p>
      )}
      {/* line-clamp-2: show at most two lines, with "…" */}
      <p className="mt-1 line-clamp-2 text-sm text-gray-600">{email.body}</p>
    </article>
  )
}
