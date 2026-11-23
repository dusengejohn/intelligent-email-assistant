import type { Email, Priority } from '../api'
import { SOURCE_LABEL } from '../priorities'
import { PriorityBadge } from './PriorityBadge'
import { PriorityPicker } from './PriorityPicker'

interface Props {
  email: Email
  inTrash: boolean // Trash view: only Restore
  busy: boolean // an action is running: buttons disabled
  onPriorityChange: (priority: Priority) => void
  onToggleHandled: () => void
  onReclassify: () => void
  onDelete: () => void
  onRestore: () => void
  onClose: () => void
}

function fullDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'short' })
}

const BUTTON =
  'rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50'

/** The open email with everything about it, and the actions (master-detail). */
export function ReadingPane({
  email,
  inTrash,
  busy,
  onPriorityChange,
  onToggleHandled,
  onReclassify,
  onDelete,
  onRestore,
  onClose,
}: Props) {
  const handled = email.status === 'handled'
  return (
    <section aria-label="Reading pane" className="flex flex-col gap-4 p-5">
      {/* On narrow screens the pane replaces the list: offer a way back */}
      <button type="button" onClick={onClose} className="self-start text-sm text-blue-700 hover:underline xl:hidden">
        ← Back to list
      </button>

      <div className="flex flex-wrap items-center gap-2">
        {inTrash ? (
          <button type="button" onClick={onRestore} disabled={busy} className={BUTTON}>
            Restore
          </button>
        ) : (
          <>
            <PriorityPicker value={email.priority} saving={busy} onChange={onPriorityChange} />
            <button type="button" onClick={onToggleHandled} disabled={busy} className={BUTTON}>
              {handled ? 'Mark as new' : 'Mark handled'}
            </button>
            <button type="button" onClick={onReclassify} disabled={busy} className={BUTTON}>
              Re-classify
            </button>
            <button
              type="button"
              onClick={onDelete}
              disabled={busy}
              className={`${BUTTON} text-red-700 hover:bg-red-50`}
            >
              Delete
            </button>
          </>
        )}
      </div>

      <header>
        <h2 className="text-lg font-semibold text-gray-900">{email.subject}</h2>
        <p className="mt-1 text-sm text-gray-700">
          <span className="font-medium">{email.sender_name}</span>{' '}
          <span className="text-gray-500">&lt;{email.sender_email}&gt;</span>
        </p>
        <p className="text-xs text-gray-500">{fullDate(email.received_at)}</p>
      </header>

      {/* Classification: badge, source, reason and the suggested reply time */}
      <div className="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm">
        <PriorityBadge email={email} />
        {email.priority_reason && <p className="mt-2 text-gray-700">{email.priority_reason}</p>}
        {email.suggested_response_minutes !== null && (
          <p className="mt-1 text-xs text-gray-500">
            Suggested reply time: {email.suggested_response_minutes} min
            {email.classification_source && ` · ${SOURCE_LABEL[email.classification_source]}`}
          </p>
        )}
      </div>

      {/* whitespace-pre-wrap keeps the email's own line breaks */}
      <p data-testid="email-body" className="text-sm whitespace-pre-wrap text-gray-800">
        {email.body}
      </p>
    </section>
  )
}
