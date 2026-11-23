// Typed client for the backend API. Components call these functions instead of
// using fetch directly, so URLs, data shapes and error handling live in one place.
// `/api` is proxied to FastAPI: by Vite in dev (:5173), by nginx in Docker (:8080).

export type Priority = 'critical' | 'high' | 'moderate' | 'low'
export type EmailStatus = 'new' | 'handled'
export type ClassificationSource = 'ai' | 'fallback' | 'manual'

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

export function generateEmails(count: number, scenario?: string): Promise<Email[]> {
  const trimmed = scenario?.trim()
  return request<Email[]>('/api/emails/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // Leave out an empty scenario rather than sending ""
    body: JSON.stringify(trimmed ? { count, scenario: trimmed } : { count }),
  })
}

/** Totals over all the classify requests of one click. */
export interface ClassifyTotals {
  classified: number
  ai: number
  fallback: number
}

interface ClassifyResult {
  classified: number
  by_source: { ai: number; fallback: number }
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
  const totals: ClassifyTotals = { classified: 0, ai: 0, fallback: 0 }
  for (let i = 0; i < MAX_CLASSIFY_REQUESTS; i++) {
    const result = await request<ClassifyResult>('/api/emails/classify', { method: 'POST' })
    totals.classified += result.classified
    totals.ai += result.by_source.ai
    totals.fallback += result.by_source.fallback
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
    return 'The server took too long to answer (HTTP 504). Try fewer emails.'
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
