// Typed client for the generator's API. The page calls these functions instead
// of using fetch directly. `/api` is the same origin: FastAPI serves the page in
// Docker; in dev Vite (:5174) proxies /api to uvicorn (:8001).
// Error handling follows the inbox's frontend/src/api.ts (a small, deliberate copy).

/** Response of POST /api/generate. */
export interface GenerateResult {
  /** Valid emails Claude produced (can be fewer than requested) */
  generated: number
  /** Emails the inbox accepted */
  delivered: number
}

/** A failed request. `message` is safe to show; `status` 0 = no response at all. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function generateEmails(count: number, scenario?: string): Promise<GenerateResult> {
  const trimmed = scenario?.trim()
  return request<GenerateResult>('/api/generate', {
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
    throw new ApiError('Cannot reach the generator. Is it running?', 0)
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
    // Not JSON
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
        const field = issue.loc?.at(-1)
        return field !== undefined ? `${field}: ${issue.msg}` : `${issue.msg}`
      })
    return parts.length > 0 ? parts.join('; ') : null
  }
  return null
}
