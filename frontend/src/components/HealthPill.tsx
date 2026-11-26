import { useEffect, useState } from 'react'

type Health = 'checking' | 'ok' | 'down'

const LABEL: Record<Health, string> = {
  checking: 'Checking backend…',
  ok: 'Backend is healthy',
  down: 'Backend unreachable',
}

const COLOR: Record<Health, string> = {
  checking: 'text-gray-500',
  ok: 'text-green-600',
  down: 'text-red-600',
}

/** How often the pill re-checks the backend (same rhythm as the new-mail polling). */
export const HEALTH_INTERVAL_MS = 15_000

/**
 * Small status pill: is the FastAPI backend reachable through /api?
 * Checked on load and then every HEALTH_INTERVAL_MS, so it turns red when the
 * backend goes away and green again when it is back, without a page reload
 * (story 3b.6: the new-mail polling stays quiet on errors, this pill shows them).
 */
export function HealthPill() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    const check = () => {
      fetch('/api/health')
        .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
        .then((data: { status: string }) => setHealth(data.status === 'ok' ? 'ok' : 'down'))
        .catch(() => setHealth('down'))
    }
    check()
    const timer = window.setInterval(check, HEALTH_INTERVAL_MS)
    return () => window.clearInterval(timer) // stop when the pill goes away
  }, [])

  return (
    <p
      role="status"
      className={`inline-flex items-center gap-2 rounded-full border border-current px-3 py-1 text-sm ${COLOR[health]}`}
    >
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      {LABEL[health]}
    </p>
  )
}
