import { useEffect, useState } from 'react'
import {
  ApiError,
  classifyEmails,
  generateEmails,
  getSummary,
  listEmails,
  updateEmail,
  type Email,
  type EmailSummary,
  type Priority,
} from './api'
import { EmailList } from './components/EmailList'
import { ErrorBanner } from './components/ErrorBanner'
import { Sidebar, ViewSelect } from './components/Sidebar'
import { Toolbar } from './components/Toolbar'
import { viewById, viewFromUrl, viewUrl, type ViewId } from './views'

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
}

function App() {
  // State: data the page remembers. Changing it redraws the page.
  // The selected view starts from the URL (?view=critical), so refresh and links keep it.
  const [view, setView] = useState<ViewId>(() => viewFromUrl(window.location.search))
  const [reloadKey, setReloadKey] = useState(0) // bump it to reload list + counts
  const [emails, setEmails] = useState<Email[]>([])
  const [summary, setSummary] = useState<EmailSummary | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [progress, setProgress] = useState(0) // emails classified so far in this click
  const [target, setTarget] = useState(0) // unclassified emails when the click started
  const [notice, setNotice] = useState<string | null>(null) // result of the last classify
  const [savingId, setSavingId] = useState<number | null>(null) // email whose priority is saving
  const [error, setError] = useState<string | null>(null)

  const current = viewById(view)
  const unclassified = summary?.unclassified ?? 0

  // Load the current view's emails and all counts, in parallel. Runs at start,
  // when the view changes and after every change (reloadKey). `cancelled` drops a
  // slow, outdated answer if the user already switched to another view.
  useEffect(() => {
    let cancelled = false
    Promise.all([listEmails(viewById(view).filter), getSummary()])
      .then(([list, counts]) => {
        if (cancelled) return
        setEmails(list)
        setSummary(counts)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(messageOf(err))
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false)
      })
    return () => {
      cancelled = true
    }
  }, [view, reloadKey])

  // Browser Back/Forward: the URL changed, so follow it
  useEffect(() => {
    const onPopState = () => setView(viewFromUrl(window.location.search))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function selectView(id: ViewId) {
    if (id === view) return
    setLoadingList(true)
    // pushState: changes the address without reloading, and adds a Back step
    window.history.pushState(null, '', viewUrl(id))
    setView(id)
  }

  function reload() {
    setReloadKey((key) => key + 1)
  }

  async function handleGenerate(count: number, scenario: string) {
    setGenerating(true)
    setError(null)
    setNotice(null)
    try {
      await generateEmails(count, scenario)
      reload() // new emails: refresh the list and the counts
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
      reload()
      setClassifying(false)
    }
  }

  async function handlePriorityChange(id: number, priority: Priority) {
    setSavingId(id)
    setError(null)
    try {
      await updateEmail(id, { priority })
      // The email may move within the view, or leave it (e.g. Critical -> High),
      // and the counts change: reload both instead of patching one row
      reload()
    } catch (err) {
      setError(messageOf(err)) // the row keeps its previous priority
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
        <Sidebar active={view} summary={summary} onSelect={selectView} />
        {/* `relative` matters: each row has a screen-reader-only label (sr-only =
            position: absolute). A scroll container only clips absolutely positioned
            children if it is itself positioned; without it those labels stuck out
            below the page and made the WHOLE page scroll into a long blank area. */}
        <main data-testid="list-scroll" className="relative min-w-0 flex-1 overflow-y-auto bg-white">
          <ViewSelect active={view} summary={summary} onSelect={selectView} />
          <EmailList
            emails={emails}
            loading={loadingList}
            savingId={savingId}
            emptyText={current.empty}
            readOnly={view === 'trash'}
            onPriorityChange={handlePriorityChange}
          />
        </main>
      </div>
    </div>
  )
}

export default App
