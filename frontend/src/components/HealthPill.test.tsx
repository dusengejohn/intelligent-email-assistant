// @vitest-environment jsdom
// The health pill re-checks the backend on a timer (story 3b.6 review): it must
// turn red when the backend goes away and green again when it is back, without
// a page reload. Fake fetch + fake clock: no server, no waiting.
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { HEALTH_INTERVAL_MS, HealthPill } from './HealthPill'

/** Fake /api/health: answers "ok" while `up.value` is true, else 502 like nginx. */
function fakeBackend() {
  const up = { value: true }
  const calls = { count: 0 }
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      calls.count += 1
      return up.value
        ? new Response(JSON.stringify({ status: 'ok' }), { status: 200 })
        : new Response('<html>502 Bad Gateway</html>', { status: 502 })
    }),
  )
  return { up, calls }
}

async function nextCheck() {
  await act(() => vi.advanceTimersByTimeAsync(HEALTH_INTERVAL_MS))
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('HealthPill', () => {
  it('checks every 15 seconds', async () => {
    const { calls } = fakeBackend()
    render(<HealthPill />)
    await screen.findByText('Backend is healthy')

    await nextCheck()
    await nextCheck()

    expect(HEALTH_INTERVAL_MS).toBe(15_000)
    expect(calls.count).toBe(3) // on load + 2 timed checks
  })

  it('turns red when the backend goes away, and green again when it is back', async () => {
    const { up } = fakeBackend()
    render(<HealthPill />)
    expect(await screen.findByText('Backend is healthy')).toBeInTheDocument()

    up.value = false
    await nextCheck()
    expect(screen.getByText('Backend unreachable')).toBeInTheDocument()

    up.value = true
    await nextCheck()
    expect(screen.getByText('Backend is healthy')).toBeInTheDocument()
  })

  it('treats a network failure as unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))

    render(<HealthPill />)

    expect(await screen.findByText('Backend unreachable')).toBeInTheDocument()
  })

  it('stops checking when it is removed (timer cleanup)', async () => {
    const { calls } = fakeBackend()
    const { unmount } = render(<HealthPill />)
    await screen.findByText('Backend is healthy')

    unmount()
    const before = calls.count
    await nextCheck()

    expect(calls.count).toBe(before)
  })
})
