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

export function listEmails(): Promise<Email[]> {
  return request<Email[]>('/api/emails')
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
