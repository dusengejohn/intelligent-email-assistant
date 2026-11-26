// Tests for the generator page's API client. `fetch` is a fake (vi.stubGlobal):
// no server or network needed.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, generateEmails } from './api'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function fakeFetch(response: Response | Error) {
  const mock = vi.fn(async () => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

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

describe('generateEmails', () => {
  it('POSTs count and scenario and returns the counts', async () => {
    const mock = fakeFetch(jsonResponse(201, { generated: 10, delivered: 10 }))

    const result = await generateEmails(10, 'IT team')

    expect(result).toEqual({ generated: 10, delivered: 10 })
    expect(mock).toHaveBeenCalledWith('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: 10, scenario: 'IT team' }),
    })
  })

  it.each([undefined, '', '   '])('leaves out an empty scenario (%j)', async (scenario) => {
    const mock = fakeFetch(jsonResponse(201, { generated: 5, delivered: 5 }))

    await generateEmails(5, scenario)

    const init = mock.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(init[1].body as string)).toEqual({ count: 5 })
  })

  it.each([
    [503, 'Delivery is not configured: set INGEST_TOKEN in .env'],
    [502, 'Generated 10 emails but the inbox could not be reached. Nothing was delivered.'],
  ])('turns HTTP %i into an ApiError with the API detail', async (status, detail) => {
    fakeFetch(jsonResponse(status, { detail }))

    const err = await apiError(() => generateEmails(10))

    expect(err.status).toBe(status)
    expect(err.message).toBe(detail)
  })

  it('turns a FastAPI 422 detail list into a readable sentence', async () => {
    fakeFetch(
      jsonResponse(422, {
        detail: [{ loc: ['body', 'count'], msg: 'Input should be less than or equal to 50' }],
      }),
    )

    const err = await apiError(() => generateEmails(51))

    expect(err.message).toBe('count: Input should be less than or equal to 50')
  })

  it('gives a generic message for a non-JSON error', async () => {
    fakeFetch(new Response('<html>oops</html>', { status: 500 }))

    const err = await apiError(() => generateEmails(1))

    expect(err.message).toBe('Request failed (HTTP 500)')
  })

  it('explains when the generator cannot be reached', async () => {
    fakeFetch(new TypeError('Failed to fetch'))

    const err = await apiError(() => generateEmails(1))

    expect(err.status).toBe(0)
    expect(err.message).toMatch(/cannot reach the generator/i)
  })
})
