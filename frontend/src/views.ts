// The sidebar views: one table used by the sidebar, the narrow-screen dropdown,
// the URL (?view=...) and the tests.
import type { EmailFilter, EmailSummary } from './api'
import { PRIORITIES } from './priorities'

export type ViewId =
  | 'plan'
  | 'all'
  | 'unclassified'
  | 'classified'
  | 'critical'
  | 'high'
  | 'moderate'
  | 'low'
  | 'trash'

export interface View {
  id: ViewId
  label: string
  filter: EmailFilter // what GET /api/emails is asked for
  countKey?: keyof EmailSummary // which /summary number belongs to it (none for the Plan)
  empty: string // message when the view has no emails
  color?: string // priority dot
}

export const VIEWS: View[] = [
  // The day's plan (Epic 4). It still loads all emails, so the reading pane can open
  // an email clicked in the plan.
  { id: 'plan', label: 'Plan', filter: {}, empty: 'Nothing to plan.' },
  { id: 'all', label: 'All', filter: {}, countKey: 'all', empty: 'No emails yet. New ones come from the Email Generator.' },
  { id: 'unclassified', label: 'Unclassified', filter: { classified: false }, countKey: 'unclassified', empty: 'Nothing to classify.' },
  { id: 'classified', label: 'Classified', filter: { classified: true }, countKey: 'classified', empty: 'No classified emails yet. Click Classify.' },
  { id: 'critical', label: PRIORITIES.critical.label, filter: { priority: 'critical' }, countKey: 'critical', empty: 'No critical emails.', color: PRIORITIES.critical.color },
  { id: 'high', label: PRIORITIES.high.label, filter: { priority: 'high' }, countKey: 'high', empty: 'No high-priority emails.', color: PRIORITIES.high.color },
  { id: 'moderate', label: PRIORITIES.moderate.label, filter: { priority: 'moderate' }, countKey: 'moderate', empty: 'No moderate emails.', color: PRIORITIES.moderate.color },
  { id: 'low', label: PRIORITIES.low.label, filter: { priority: 'low' }, countKey: 'low', empty: 'No low-priority emails.', color: PRIORITIES.low.color },
  { id: 'trash', label: 'Trash', filter: { trash: true }, countKey: 'trash', empty: 'Trash is empty.' },
]

export function viewById(id: ViewId): View {
  return VIEWS.find((view) => view.id === id) ?? VIEWS[0]
}

/** "?view=critical" -> "critical"; anything unknown or missing -> "all". */
export function viewFromUrl(search: string): ViewId {
  const id = new URLSearchParams(search).get('view')
  return VIEWS.some((view) => view.id === id) ? (id as ViewId) : 'all'
}

/** The address for a view: a clean "/" for All, "/?view=..." for the others. */
export function viewUrl(id: ViewId): string {
  return id === 'all' ? '/' : `/?view=${id}`
}
