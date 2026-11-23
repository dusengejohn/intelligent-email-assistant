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
import { Sidebar } from './components/Sidebar'
import { Toolbar } from './components/Toolbar'

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

  // Status line under the toolbar: progress, result of the last action, or a hint
  const statusText = generating
    ? 'Claude is writing your emails. This can take 15 seconds or more…'
    : classifying
      ? `Classifying… ${progress} of ${target}`
      : (notice ?? `${unclassified} unclassified`)

  // App shell: the page itself never scrolls (h-screen); only the list does.
  // min-h-0 / min-w-0 let flex children shrink so overflow-y-auto can work.
  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <Toolbar
        generating={generating}
        classifying={classifying}
        loadingList={loadingList}
        onGenerate={handleGenerate}
        onClassify={handleClassify}
      />
      <p className="border-b border-gray-200 bg-white px-4 py-1 text-xs text-gray-600" role="status">
        {statusText}
      </p>
      {error && (
        <div className="px-4 pt-3">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        <Sidebar total={loadingList ? null : emails.length} />
        <main className="min-w-0 flex-1 overflow-y-auto bg-white">
          <EmailList
            emails={emails}
            loading={loadingList}
            savingId={savingId}
            onPriorityChange={handlePriorityChange}
          />
        </main>
      </div>
    </div>
  )
}

export default App
