import type { Priority } from '../api'
import { PRIORITIES, PRIORITY_ORDER } from '../priorities'

interface Props {
  value: Priority | null
  saving: boolean
  onChange: (priority: Priority) => void
}

/** Manual override: a native <select>, so it works with the keyboard too. */
export function PriorityPicker({ value, saving, onChange }: Props) {
  return (
    <label className="text-xs text-gray-500">
      <span className="sr-only">Change priority</span>
      <select
        value={value ?? ''}
        disabled={saving}
        onChange={(e) => onChange(e.target.value as Priority)}
        className="rounded border border-gray-300 bg-white px-1 py-0.5 text-xs text-gray-700 disabled:opacity-50"
      >
        {value === null && (
          <option value="" disabled>
            Set priority…
          </option>
        )}
        {PRIORITY_ORDER.map((p) => (
          <option key={p} value={p}>
            {PRIORITIES[p].label}
          </option>
        ))}
      </select>
    </label>
  )
}
