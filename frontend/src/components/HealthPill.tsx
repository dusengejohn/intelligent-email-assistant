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

/** Small status pill: is the FastAPI backend reachable through /api? */
export function HealthPill() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data: { status: string }) => setHealth(data.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
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
