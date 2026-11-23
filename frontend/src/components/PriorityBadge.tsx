import type { Email } from '../api'
import { PRIORITIES, SOURCE_LABEL } from '../priorities'

/**
 * Priority badge: colored dot + border with DARK text. The text carries the
 * meaning and the color reinforces it (white text on the brief's yellow would be
 * too hard to read, and color alone doesn't work for color-blind users).
 */
export function PriorityBadge({ email }: { email: Email }) {
  if (email.priority === null) {
    return (
      <span className="inline-flex items-center rounded-full border border-gray-300 px-2 py-0.5 text-xs text-gray-500">
        Not classified
      </span>
    )
  }
  const { label, color } = PRIORITIES[email.priority]
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span
        className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-semibold text-gray-900"
        style={{ borderColor: color }}
      >
        <span aria-hidden="true" className="size-2 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </span>
      {email.classification_source && (
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
          {SOURCE_LABEL[email.classification_source]}
        </span>
      )}
    </span>
  )
}
