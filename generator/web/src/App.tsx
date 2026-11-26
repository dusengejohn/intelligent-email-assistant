import { useState, type FormEvent } from 'react'
import { ApiError, generateEmails } from './api'
import { MAX_COUNT, MIN_COUNT, resultText } from './result'

// Written into the page at build time (VITE_INBOX_URL); the Docker default port
const INBOX_URL: string = import.meta.env.VITE_INBOX_URL ?? 'http://localhost:8080'

type Outcome =
  | { kind: 'idle' }
  | { kind: 'running' }
  | { kind: 'done'; requested: number; generated: number; delivered: number }
  | { kind: 'failed'; message: string }

/** The whole page: a search-engine-style form, and the result below it. */
export default function App() {
  // Kept as text while typing, so the field can be briefly empty
  const [count, setCount] = useState('10')
  const [scenario, setScenario] = useState('')
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  const value = Number(count)
  const valid = count !== '' && Number.isInteger(value) && value >= MIN_COUNT && value <= MAX_COUNT
  const running = outcome.kind === 'running'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault() // stay on the page (no full-page form submit)
    if (!valid || running) return
    setOutcome({ kind: 'running' })
    try {
      const result = await generateEmails(value, scenario)
      setOutcome({ kind: 'done', requested: value, ...result })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Something went wrong.'
      setOutcome({ kind: 'failed', message })
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center bg-white px-4 pt-[18vh] text-gray-900">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
        <span className="text-blue-600">Email</span> Generator
      </h1>
      <p className="mt-3 text-center text-gray-500">
        Sample workplace emails, written by Claude and delivered to your inbox.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-8 flex w-full max-w-2xl items-center gap-2 rounded-full border border-gray-300 py-2 pr-2 pl-5 shadow-sm focus-within:shadow-md"
      >
        <label className="flex items-center gap-1 text-sm text-gray-500">
          <span className="sr-only">How many emails</span>
          <input
            type="number"
            min={MIN_COUNT}
            max={MAX_COUNT}
            step={1}
            required
            value={count}
            onChange={(e) => setCount(e.target.value)}
            disabled={running}
            className="w-14 bg-transparent text-base text-gray-900 outline-none invalid:text-red-600"
          />
          <span aria-hidden="true">emails</span>
        </label>
        <span className="h-6 w-px bg-gray-200" aria-hidden="true" />
        <label className="min-w-0 flex-1">
          <span className="sr-only">Scenario (optional)</span>
          <input
            type="text"
            maxLength={200}
            placeholder="Scenario (optional), e.g. hospital IT team"
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            disabled={running}
            className="w-full bg-transparent text-base outline-none placeholder:text-gray-400"
          />
        </label>
        <button
          type="submit"
          disabled={running || !valid}
          className="rounded-full bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? 'Generating…' : 'Generate'}
        </button>
      </form>

      <div className="mt-8 w-full max-w-2xl text-center">
        {running && (
          <p role="status" className="text-gray-500">
            Writing emails with Claude… (about 15 s per 10 emails)
          </p>
        )}
        {outcome.kind === 'done' && (
          <div role="status">
            <p className="text-lg font-medium text-green-700">
              {resultText(outcome.requested, outcome.delivered)}
            </p>
            {/* A new tab: the generator stays open for the next run. noopener: the
                inbox page gets no handle back to this one (window.opener) */}
            <a
              href={INBOX_URL}
              target="_blank"
              rel="noopener"
              className="mt-2 inline-block text-blue-600 underline hover:text-blue-800"
            >
              Open the inbox ↗
            </a>
          </div>
        )}
        {outcome.kind === 'failed' && (
          <p
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-left text-red-800"
          >
            {outcome.message}
          </p>
        )}
      </div>
    </main>
  )
}
