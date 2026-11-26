import type { EmailSummary } from '../api'
import { VIEWS, type ViewId } from '../views'

interface Props {
  active: ViewId
  summary: EmailSummary | null // null while loading: no numbers yet
  onSelect: (id: ViewId) => void
}

/**
 * The views on the left, each with its count from GET /api/emails/summary.
 * Real <button>s inside a <nav>: Tab reaches them, Enter opens them, and
 * aria-current tells screen readers which view is selected. Hidden on narrow
 * screens, where <ViewSelect> takes its place.
 */
export function Sidebar({ active, summary, onSelect }: Props) {
  return (
    <nav aria-label="Views" className="hidden w-52 shrink-0 overflow-y-auto border-r border-gray-200 p-3 md:block">
      <ul className="flex flex-col gap-0.5">
        {VIEWS.map((view) => {
          const selected = view.id === active
          return (
            <li key={view.id}>
              {/* A gap before the priorities and before the Trash groups the list */}
              {(view.id === 'all' || view.id === 'critical' || view.id === 'trash') && (
                <hr className="my-2 border-gray-200" />
              )}
              <button
                type="button"
                onClick={() => onSelect(view.id)}
                aria-current={selected ? 'page' : undefined}
                className={`flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm ${
                  selected ? 'bg-blue-50 font-semibold text-blue-800' : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                {view.color && (
                  <span aria-hidden="true" className="size-2 rounded-full" style={{ backgroundColor: view.color }} />
                )}
                {view.id === 'trash' && <span aria-hidden="true">🗑</span>}
                {view.id === 'plan' && <span aria-hidden="true">📅</span>}
                <span className="flex-1">{view.label}</span>
                {summary && view.countKey && (
                  <span className="text-xs text-gray-500">{summary[view.countKey]}</span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** The same views as a dropdown, for narrow screens (the sidebar is hidden there). */
export function ViewSelect({ active, summary, onSelect }: Props) {
  return (
    <label className="block border-b border-gray-200 bg-white px-3 py-2 md:hidden">
      <span className="sr-only">View</span>
      <select
        value={active}
        onChange={(e) => onSelect(e.target.value as ViewId)}
        className="w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm"
      >
        {VIEWS.map((view) => (
          <option key={view.id} value={view.id}>
            {view.label}
            {summary && view.countKey ? ` (${summary[view.countKey]})` : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
