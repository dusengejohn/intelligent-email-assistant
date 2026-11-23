import { useEffect, useState } from 'react'
import {
  ApiError,
  classifyEmails,
  generateEmails,
  listEmails,
  updateEmail,
  type Email,
  type Priority,
} from './api'
import { EmailList } from './components/EmailList'
import { ErrorBanner } from './components/ErrorBanner'
import { GenerateControls } from './components/GenerateControls'
import { HealthPill } from './components/HealthPill'

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
}

function App() {
  // State: data the page remembers. Changing it redraws the page.
  const [emails, setEmails] = useState<Email[]>([])
  const [loadingList, setLoadingList] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [progress, setProgress] = useState(0) // emails classified so far in this click
  const [target, setTarget] = useState(0) // unclassified emails when the click started
  const [notice, setNotice] = useState<string | null>(null) // result of the last classify
  const [savingId, setSavingId] = useState<number | null>(null) // email whose priority is saving
  const [error, setError] = useState<string | null>(null)

  // Generate and Classify both change the list: never run them at the same time
  const busy = generating || classifying
  const unclassified = emails.filter((e) => e.priority === null).length

  // Runs once after the first render: load the stored emails
  useEffect(() => {
    listEmails()
      .then(setEmails)
      .catch((err: unknown) => setError(messageOf(err)))
      .finally(() => setLoadingList(false))
  }, [])

  async function handleGenerate(count: number, scenario: string) {
    setGenerating(true)
    setError(null)
    setNotice(null)
    try {
      await generateEmails(count, scenario)
      setEmails(await listEmails()) // refresh: show the new emails in list order
    } catch (err) {
      setError(messageOf(err)) // the existing list stays as it was
    } finally {
      setGenerating(false)
    }
  }

  async function handleClassify() {
    setClassifying(true)
    setProgress(0)
    setTarget(unclassified)
    setError(null)
    setNotice(null)
    try {
      // Repeats the request until nothing is left (the backend does 50 at a time)
      const totals = await classifyEmails(setProgress)
      setNotice(
        totals.classified === 0
          ? 'Nothing to classify: every email already has a priority.'
          : `Classified ${totals.classified} emails: ${totals.ai} by AI, ${totals.fallback} by rules.`,
      )
    } catch (err) {
      setError(messageOf(err))
    } finally {
      // Refresh even after an error: earlier requests may have saved results
      try {
        setEmails(await listEmails())
      } catch {
        // keep the current list; the error banner already explains the problem
      }
      setClassifying(false)
    }
  }

  async function handlePriorityChange(id: number, priority: Priority) {
    setSavingId(id)
    setError(null)
    try {
      // Confirmed update: show the server's version once it has saved it
      const updated = await updateEmail(id, { priority })
      setEmails((current) => current.map((e) => (e.id === id ? updated : e)))
    } catch (err) {
      setError(messageOf(err)) // the card keeps its previous priority
    } finally {
      setSavingId(null)
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Intelligent Email Assistant</h1>
        <HealthPill />
      </header>

      <section className="flex flex-col gap-2">
        <GenerateControls generating={generating} disabled={classifying} onGenerate={handleGenerate} />
        {generating && (
          <p className="text-sm text-gray-500">
            Claude is writing your emails. This can take 15 seconds or more…
          </p>
        )}
      </section>

      <section className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleClassify}
          disabled={busy || loadingList}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {classifying ? 'Classifying…' : 'Classify'}
        </button>
        <p className="text-sm text-gray-600" role="status">
          {classifying
            ? `Classifying… ${progress} of ${target}`
            : (notice ?? `${unclassified} unclassified`)}
        </p>
      </section>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Emails {!loadingList && <span className="text-gray-500">({emails.length})</span>}
        </h2>
        <EmailList
          emails={emails}
          loading={loadingList}
          savingId={savingId}
          onPriorityChange={handlePriorityChange}
        />
      </section>
    </main>
  )
}

export default App
