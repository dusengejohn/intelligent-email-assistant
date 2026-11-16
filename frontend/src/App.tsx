import { useEffect, useState } from 'react'
import './App.css'

type Health = 'checking' | 'ok' | 'down'

function App() {
  const [health, setHealth] = useState<Health>('checking')

  useEffect(() => {
    // /api is proxied to FastAPI: by Vite in dev, by nginx in Docker
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data: { status: string }) => setHealth(data.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  const label = {
    checking: 'Checking backend…',
    ok: 'Backend is healthy',
    down: 'Backend unreachable',
  }[health]

  return (
    <main className="app">
      <h1>Intelligent Email Assistant</h1>
      <p className={`health health--${health}`} role="status">
        <span className="dot" aria-hidden="true" />
        {label}
      </p>
    </main>
  )
}

export default App
