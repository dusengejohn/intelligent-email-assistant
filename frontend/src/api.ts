// Typed client for the backend API. Components call these functions instead of
// using fetch directly, so URLs, data shapes and error handling live in one place.
// `/api` is proxied to FastAPI: by Vite in dev (:5173), by nginx in Docker (:8080).

export type Priority = 'critical' | 'high' | 'moderate' | 'low'
export type EmailStatus = 'new' | 'handled'
/** 'ai' only on emails classified by Claude before #92; new results are 'rules'. */
export type ClassificationSource = 'ai' | 'rules' | 'manual'

/** Matches the backend's `EmailRead` schema. Timestamps are UTC ISO strings. */
export interface Email {
  id: number
  sender_name: string
  sender_email: string
  subject: string
  body: string
  received_at: string
  priority: Priority | null
  priority_reason: string | null
  classification_source: ClassificationSource | null
  suggested_response_minutes: number | null
  status: EmailStatus
  created_at: string
  /** Set when the email is in the Trash (soft delete); null while active. */
  deleted_at: string | null
}

/** A failed request. `message` is safe to show to the user; `status` 0 = no response. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Counts for the sidebar views (GET /api/emails/summary). */
export interface EmailSummary {
  all: number
  unclassified: number
  classified: number
  critical: number
  high: number
  moderate: number
  low: number
  handled: number
  trash: number
}

/** Optional filters for the list; each sidebar view is one combination. */
export interface EmailFilter {
  priority?: Priority
  classified?: boolean
  trash?: boolean
}

export function listEmails(filter: EmailFilter = {}): Promise<Email[]> {
  const params = new URLSearchParams()
  if (filter.priority) params.set('priority', filter.priority)
  if (filter.classified !== undefined) params.set('classified', String(filter.classified))
  if (filter.trash) params.set('trash', 'true')
  const query = params.toString()
  return request<Email[]>(query ? `/api/emails?${query}` : '/api/emails')
}

export function getSummary(): Promise<EmailSummary> {
  return request<EmailSummary>('/api/emails/summary')
}

/** Totals over all the classify requests of one click. */
export interface ClassifyTotals {
  classified: number
  /** New urgent emails among those just classified (for the alert, story 3.7) */
  critical: number
  high: number
}

interface ClassifyResult {
  classified: number
  remaining: number
  emails: Email[]
}

// Safety net: 20 requests x 50 emails = 1,000 emails per click at most
const MAX_CLASSIFY_REQUESTS = 20

/**
 * Classify every unclassified email. The backend does at most 50 per request
 * and says how many are `remaining`, so call again until it's 0.
 * `onProgress` gets the running total after each request.
 */
export async function classifyEmails(
  onProgress?: (classifiedSoFar: number) => void,
): Promise<ClassifyTotals> {
  const totals: ClassifyTotals = { classified: 0, critical: 0, high: 0 }
  for (let i = 0; i < MAX_CLASSIFY_REQUESTS; i++) {
    const result = await request<ClassifyResult>('/api/emails/classify', { method: 'POST' })
    totals.classified += result.classified
    // Counted from the emails this request classified: exact, unlike comparing
    // /summary totals before/after (other changes could happen meanwhile)
    totals.critical += result.emails.filter((e) => e.priority === 'critical').length
    totals.high += result.emails.filter((e) => e.priority === 'high').length
    onProgress?.(totals.classified)
    // Done, or no progress (would otherwise loop forever)
    if (result.remaining === 0 || result.classified === 0) break
  }
  return totals
}

/** Fields that PATCH /api/emails/{id} accepts; send only what changes. */
export interface EmailChanges {
  priority?: Priority
  status?: EmailStatus
}

export function updateEmail(id: number, changes: EmailChanges): Promise<Email> {
  return request<Email>(`/api/emails/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
}

/** Move one email to the Trash (204, no body). */
export function deleteEmail(id: number): Promise<void> {
  return request<void>(`/api/emails/${id}`, { method: 'DELETE' })
}

/** Bring an email back from the Trash, unchanged. */
export function restoreEmail(id: number): Promise<Email> {
  return request<Email>(`/api/emails/${id}/restore`, { method: 'POST' })
}

/** Permanently delete everything in the Trash. */
export function emptyTrash(): Promise<{ deleted: number }> {
  return request<{ deleted: number }>('/api/emails/trash', { method: 'DELETE' })
}

/** Classify one email by keywords ("Classify by keywords"), whatever it had before. */
export function classifyOne(id: number): Promise<Email> {
  return request<Email>(`/api/emails/${id}/classify`, { method: 'POST' })
}

// --- Planning (Epic 4) ---------------------------------------------------------------
// All times are UTC ISO strings; show them in `Plan.timezone` (APP_TIMEZONE).

export interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
}

export interface PlanEmail {
  id: number
  subject: string
  priority: Priority
  /** Suggested time to reply */
  minutes: number
}

/** When to answer what: one email, or the batch of low emails. */
export interface PlanBlock {
  start: string
  end: string
  priority: Priority
  emails: PlanEmail[]
}

/** GET /api/planning/suggestions: advice only, nothing is booked. */
export interface Plan {
  /** The planned day, YYYY-MM-DD in `timezone` */
  date: string
  timezone: string
  /** Working hours still ahead; null when the day is over */
  window: { start: string; end: string } | null
  events: CalendarEvent[]
  free_slots: { start: string; end: string; minutes: number }[]
  suggestions: PlanBlock[]
  not_today: PlanEmail[]
  unclassified: number
}

/** The plan for `date` (YYYY-MM-DD), or for today when left out. */
export function getPlanning(date?: string): Promise<Plan> {
  return request<Plan>(date ? `/api/planning/suggestions?date=${date}` : '/api/planning/suggestions')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    // fetch only throws when there is no HTTP response at all
    throw new ApiError('Cannot reach the server. Is the backend running?', 0)
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status)
  }
  if (response.status === 204) {
    return undefined as T // 204 No Content: success, there is no body to read
  }
  return (await response.json()) as T
}

/** FastAPI sends errors as `{"detail": ...}`; anything else gets a generic message. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    const detail = formatDetail((body as { detail?: unknown }).detail)
    if (detail) return detail
  } catch {
    // Not JSON, e.g. an HTML error page from nginx
  }
  if (response.status === 504) {
    return 'The server took too long to answer (HTTP 504). Please try again.'
  }
  return `Request failed (HTTP ${response.status})`
}

interface ValidationIssue {
  loc?: (string | number)[]
  msg?: string
}

/** A string detail is shown as is; a 422 list becomes "field: message; ...". */
function formatDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationIssue[])
      .filter((issue) => issue.msg)
      .map((issue) => {
        const field = issue.loc?.at(-1) // ["body", "count"] -> "count"
        return field !== undefined ? `${field}: ${issue.msg}` : `${issue.msg}`
      })
    return parts.length > 0 ? parts.join('; ') : null
  }
  return null
}
