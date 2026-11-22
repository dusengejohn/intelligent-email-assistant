// Tests for the typed API client. `fetch` is replaced by a fake (vi.stubGlobal),
// so no server or network is needed.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, generateEmails, listEmails, type Email } from './api'

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
