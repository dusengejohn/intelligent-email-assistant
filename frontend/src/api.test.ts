// Tests for the typed API client. `fetch` is replaced by a fake (vi.stubGlobal),
// so no server or network is needed.
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  classifyEmails,
  classifyOne,
  deleteEmail,
  emptyTrash,
  generateEmails,
  getSummary,
  listEmails,
  restoreEmail,
  updateEmail,
  type Email,
} from './api'
import { PRIORITY_ORDER } from './priorities'

const EMAIL: Email = {
  id: 1,
  sender_name: 'Priya Raman',
  sender_email: 'priya.raman@example.com',
  subject: 'Production database latency spike',
  body: 'The orders cluster is slow.',
  received_at: '2026-11-17T19:04:25Z',
  priority: null,
  priority_reason: null,
  classification_source: null,
  suggested_response_minutes: null,
  status: 'new',
  created_at: '2026-11-17T19:05:00Z',
  deleted_at: null,
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Install a fake fetch that returns `response` (or throws it) and records calls. */
function fakeFetch(response: Response | Error) {
  const mock = vi.fn(async () => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/** Run `call`, expect it to throw an ApiError, and return that error. */
async function apiError(call: () => Promise<unknown>): Promise<ApiError> {
  try {
    await call()
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError)
    return err as ApiError
  }
  throw new Error('expected an ApiError')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('listEmails', () => {
  it('returns the parsed list from GET /api/emails', async () => {
    const mock = fakeFetch(jsonResponse(200, [EMAIL]))

    const emails = await listEmails()

    expect(emails).toEqual([EMAIL])
    expect(mock).toHaveBeenCalledWith('/api/emails', undefined)
  })
})

describe('generateEmails', () => {
  it('POSTs count and scenario as JSON', async () => {
    const mock = fakeFetch(jsonResponse(201, [EMAIL]))

    const emails = await generateEmails(10, 'IT team')

    expect(emails).toEqual([EMAIL])
    expect(mock).toHaveBeenCalledWith('/api/emails/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: 10, scenario: 'IT team' }),
    })
  })

  it.each([undefined, '', '   '])('leaves out an empty scenario (%j)', async (scenario) => {
    const mock = fakeFetch(jsonResponse(201, []))

    await generateEmails(5, scenario)

    const init = mock.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(init[1].body as string)).toEqual({ count: 5 })
  })

  it.each([
    [503, 'AI is not configured: set ANTHROPIC_API_KEY in .env'],
    [502, 'AI service error: request timed out; try again.'],
  ])('turns HTTP %i into an ApiError with the backend detail', async (status, detail) => {
    fakeFetch(jsonResponse(status, { detail }))

    const err = await apiError(() => generateEmails(10))

    expect(err.status).toBe(status)
    expect(err.message).toBe(detail)
  })

  it('turns a FastAPI 422 detail list into a readable sentence', async () => {
    fakeFetch(
      jsonResponse(422, {
        detail: [
          {
            type: 'less_than_equal',
            loc: ['body', 'count'],
            msg: 'Input should be less than or equal to 50',
            input: 51,
          },
        ],
      }),
    )

    const err = await apiError(() => generateEmails(51))

    expect(err.status).toBe(422)
    expect(err.message).toBe('count: Input should be less than or equal to 50')
  })

  it('explains a gateway timeout (non-JSON body from nginx)', async () => {
    fakeFetch(new Response('<html>504 Gateway Time-out</html>', { status: 504 }))

    const err = await apiError(() => generateEmails(50))

    expect(err.status).toBe(504)
    expect(err.message).toMatch(/took too long.*HTTP 504/)
  })

  it('gives a generic message for other non-JSON errors', async () => {
    fakeFetch(new Response('oops', { status: 500 }))

    const err = await apiError(() => generateEmails(1))

    expect(err.message).toBe('Request failed (HTTP 500)')
  })

  it('explains when the server cannot be reached', async () => {
    fakeFetch(new TypeError('Failed to fetch'))

    const err = await apiError(() => listEmails())

    expect(err.status).toBe(0)
    expect(err.message).toMatch(/cannot reach the server/i)
  })
})

/** Fake fetch returning `responses` in order (one per call). */
function fakeFetchSequence(...responses: Response[]) {
  const mock = vi.fn(async () => {
    const next = responses.shift()
    if (!next) throw new Error('fakeFetchSequence: no more responses')
    return next
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/** One POST /api/emails/classify answer. */
function classifyAnswer(classified: number, ai: number, remaining: number): Response {
  return jsonResponse(200, {
    classified,
    by_source: { ai, fallback: classified - ai },
    remaining,
    emails: [],
  })
}

describe('classifyEmails', () => {
  it('calls again until remaining is 0 and adds up the totals', async () => {
    const mock = fakeFetchSequence(
      classifyAnswer(50, 50, 55),
      classifyAnswer(50, 48, 5),
      classifyAnswer(5, 5, 0),
    )
    const progress: number[] = []

    const totals = await classifyEmails((done) => progress.push(done))

    expect(totals).toEqual({ classified: 105, ai: 103, fallback: 2, critical: 0, high: 0 })
    expect(mock).toHaveBeenCalledTimes(3)
    expect(mock).toHaveBeenCalledWith('/api/emails/classify', { method: 'POST' })
    expect(progress).toEqual([50, 100, 105])
  })

  it('makes one call when there is nothing to classify', async () => {
    const mock = fakeFetchSequence(classifyAnswer(0, 0, 0))

    expect(await classifyEmails()).toEqual({
      classified: 0,
      ai: 0,
      fallback: 0,
      critical: 0,
      high: 0,
    })
    expect(mock).toHaveBeenCalledTimes(1)
  })

  it('stops when a call makes no progress (guards against an endless loop)', async () => {
    const mock = fakeFetchSequence(classifyAnswer(10, 10, 5), classifyAnswer(0, 0, 5))

    const totals = await classifyEmails()

    expect(totals.classified).toBe(10)
    expect(mock).toHaveBeenCalledTimes(2)
  })

  it('stops after at most 20 requests', async () => {
    const answers = Array.from({ length: 25 }, () => classifyAnswer(50, 50, 999))
    const mock = fakeFetchSequence(...answers)

    const totals = await classifyEmails()

    expect(mock).toHaveBeenCalledTimes(20)
    expect(totals.classified).toBe(1000)
  })

  it('passes on a backend error', async () => {
    fakeFetchSequence(classifyAnswer(50, 50, 55), jsonResponse(502, { detail: 'AI service error: x' }))

    const err = await apiError(() => classifyEmails())

    expect(err.status).toBe(502)
    expect(err.message).toBe('AI service error: x')
  })
})

describe('updateEmail', () => {
  it('PATCHes only the given fields and returns the updated email', async () => {
    const updated = { ...EMAIL, id: 7, priority: 'high', classification_source: 'manual' }
    const mock = fakeFetch(jsonResponse(200, updated))

    const result = await updateEmail(7, { priority: 'high' })

    expect(result).toEqual(updated)
    expect(mock).toHaveBeenCalledWith('/api/emails/7', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ priority: 'high' }),
    })
  })

  it.each([
    [404, 'Email not found'],
    [422, 'priority: Input should be critical, high, moderate or low'],
  ])('turns HTTP %i into an ApiError', async (status, detail) => {
    fakeFetch(jsonResponse(status, { detail }))

    const err = await apiError(() => updateEmail(7, { priority: 'high' }))

    expect(err.status).toBe(status)
    expect(err.message).toBe(detail)
  })
})

describe('priorities', () => {
  it('lists the four priorities, most urgent first (brief §7)', () => {
    expect(PRIORITY_ORDER).toEqual(['critical', 'high', 'moderate', 'low'])
  })
})

describe('listEmails with a view filter', () => {
  it.each([
    [{ priority: 'critical' as const }, '/api/emails?priority=critical'],
    [{ classified: false }, '/api/emails?classified=false'],
    [{ classified: true }, '/api/emails?classified=true'],
    [{ trash: true }, '/api/emails?trash=true'],
  ])('builds the query string for %j', async (filter, url) => {
    const mock = fakeFetch(jsonResponse(200, []))

    await listEmails(filter)

    expect(mock).toHaveBeenCalledWith(url, undefined)
  })
})

describe('getSummary', () => {
  it('loads the view counts', async () => {
    const counts = { all: 3, unclassified: 1, classified: 2, critical: 1, high: 1, moderate: 0, low: 0, handled: 0, trash: 1 }
    const mock = fakeFetch(jsonResponse(200, counts))

    expect(await getSummary()).toEqual(counts)
    expect(mock).toHaveBeenCalledWith('/api/emails/summary', undefined)
  })
})

describe('single-email actions and the Trash', () => {
  it('deleteEmail sends DELETE and accepts 204 No Content (empty body)', async () => {
    const mock = fakeFetch(new Response(null, { status: 204 }))

    await expect(deleteEmail(7)).resolves.toBeUndefined()
    expect(mock).toHaveBeenCalledWith('/api/emails/7', { method: 'DELETE' })
  })

  it('restoreEmail posts to /restore and returns the email', async () => {
    const mock = fakeFetch(jsonResponse(200, EMAIL))

    expect(await restoreEmail(1)).toEqual(EMAIL)
    expect(mock).toHaveBeenCalledWith('/api/emails/1/restore', { method: 'POST' })
  })

  it('emptyTrash deletes the Trash and returns how many', async () => {
    const mock = fakeFetch(jsonResponse(200, { deleted: 2 }))

    expect(await emptyTrash()).toEqual({ deleted: 2 })
    expect(mock).toHaveBeenCalledWith('/api/emails/trash', { method: 'DELETE' })
  })

  it('classifyOne re-classifies one email', async () => {
    const mock = fakeFetch(jsonResponse(200, EMAIL))

    expect(await classifyOne(1)).toEqual(EMAIL)
    expect(mock).toHaveBeenCalledWith('/api/emails/1/classify', { method: 'POST' })
  })

  it('a 404 on delete becomes an ApiError', async () => {
    fakeFetch(jsonResponse(404, { detail: 'Email not found' }))

    const err = await apiError(() => deleteEmail(999))

    expect(err.status).toBe(404)
    expect(err.message).toBe('Email not found')
  })
})

describe('classifyEmails counts new urgent emails (for alerts)', () => {
  it('adds up the critical and high emails across requests', async () => {
    const answer = (priorities: Email['priority'][], remaining: number) =>
      jsonResponse(200, {
        classified: priorities.length,
        by_source: { ai: priorities.length, fallback: 0 },
        remaining,
        emails: priorities.map((priority, i) => ({ ...EMAIL, id: i, priority })),
      })
    fakeFetchSequence(answer(['critical', 'high', 'low'], 2), answer(['critical', 'moderate'], 0))

    const totals = await classifyEmails()

    expect(totals.critical).toBe(2)
    expect(totals.high).toBe(1)
  })
})
