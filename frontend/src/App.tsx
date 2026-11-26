import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  classifyEmails,
  classifyOne,
  deleteEmail,
  emptyTrash,
  getSummary,
  listEmails,
  restoreEmail,
  updateEmail,
  type Email,
  type EmailSummary,
  type Priority,
} from './api'
import { alertMessage, alertView } from './alerts'
import { arrivalMessage, arrived, POLL_INTERVAL_MS } from './arrivals'
import { ConfirmDialog } from './components/ConfirmDialog'
import { EmailList } from './components/EmailList'
import { ErrorBanner } from './components/ErrorBanner'
import { ReadingPane } from './components/ReadingPane'
import { Sidebar, ViewSelect } from './components/Sidebar'
import { Toast } from './components/Toast'
import { Toolbar } from './components/Toolbar'
import { notify } from './notifications'
import { nextSelection } from './selection'
import { viewById, viewFromUrl, viewUrl, type ViewId } from './views'

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
}

interface ToastState {
  message: string
  actionLabel?: string
  onAction?: () => void
}

function App() {
  // State: data the page remembers. Changing it redraws the page.
  // The selected view starts from the URL (?view=critical), so refresh and links keep it.
  const [view, setView] = useState<ViewId>(() => viewFromUrl(window.location.search))
  const [reloadKey, setReloadKey] = useState(0) // bump it to reload list + counts
  const [emails, setEmails] = useState<Email[]>([])
  const [summary, setSummary] = useState<EmailSummary | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null) // email in the reading pane
  const [loadingList, setLoadingList] = useState(true)
  const [classifying, setClassifying] = useState(false)
  const [busy, setBusy] = useState(false) // a reading-pane action is running
  const [progress, setProgress] = useState(0) // emails classified so far in this click
  const [target, setTarget] = useState(0) // unclassified emails when the click started
  const [notice, setNotice] = useState<string | null>(null) // result of the last classify
  const [toast, setToast] = useState<ToastState | null>(null)
  const [confirmEmpty, setConfirmEmpty] = useState(false) // "Empty trash?" dialog open
  const [error, setError] = useState<string | null>(null)
  // The ids of the list as last shown, to find "the next email" after one leaves
  const shownIds = useRef<number[]>([])
  // The counts last seen, to notice mail that arrived since (story 3b.5)
  const lastSummary = useRef<EmailSummary | null>(null)

  /**
   * Every new set of counts (page load, reload or poll) goes through here. If mail
   * arrived, reload the list and say so. useCallback with no dependencies: it only
   * uses a ref and state setters, so it is the same function on every render and
   * the polling timer below never holds an outdated copy.
   */
  const receivedSummary = useCallback((counts: EmailSummary) => {
    const count = arrived(lastSummary.current, counts)
    lastSummary.current = counts
    setSummary(counts)
    if (count === 0) return
    const message = arrivalMessage(count)
    setReloadKey((key) => key + 1) // the new emails: reload list + counts
    setNotice(message) // the status line always says it...
    setToast((showing) => showing ?? { message }) // ...the toast only if none is up (e.g. Undo)
    notify('New email', message, () => window.focus())
  }, [])

  const current = viewById(view)
  const inTrash = view === 'trash'
  const unclassified = summary?.unclassified ?? 0
  const selected = emails.find((e) => e.id === selectedId) ?? null

  // Load the current view's emails and all counts, in parallel. Runs at start,
  // when the view changes and after every change (reloadKey). `cancelled` drops a
  // slow, outdated answer if the user already switched to another view.
  useEffect(() => {
    let cancelled = false
    Promise.all([listEmails(viewById(view).filter), getSummary()])
      .then(([list, counts]) => {
        if (cancelled) return
        const ids = list.map((e) => e.id)
        // Copy the OLD ids now: React runs the updater below later (during the next
        // render), when shownIds.current already holds the NEW list
        const previousIds = shownIds.current
        // The open email left this view (deleted, restored, re-prioritised...):
        // open the one below it instead, or above, or close the pane
        setSelectedId((open) => {
          if (open === null || ids.includes(open)) return open
          const next = nextSelection(previousIds, open)
          return next !== null && ids.includes(next) ? next : null
        })
        shownIds.current = ids
        setEmails(list)
        receivedSummary(counts)
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
  }, [view, reloadKey, receivedSummary])

  // New mail: every POLL_INTERVAL_MS ask for the counts (cheap, no AI). If mail
  // arrived, receivedSummary() reloads the list. The cleanup stops the timer when
  // the page goes away, so no timer keeps running in the background.
  useEffect(() => {
    const timer = window.setInterval(() => {
      getSummary()
        .then(receivedSummary)
        .catch(() => {
          // Quiet: the health pill shows an outage; the next poll tries again
        })
    }, POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [receivedSummary])

  // Browser Back/Forward: the URL changed, so follow it
  useEffect(() => {
    const onPopState = () => {
      setSelectedId(null)
      setView(viewFromUrl(window.location.search))
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function selectView(id: ViewId) {
    if (id === view) return
    setLoadingList(true)
    setSelectedId(null) // a new view starts without an open email
    // pushState: changes the address without reloading, and adds a Back step
    window.history.pushState(null, '', viewUrl(id))
    setView(id)
  }

  function reload() {
    setReloadKey((key) => key + 1)
  }

  const closeToast = useCallback(() => setToast(null), [])

  /** Run one reading-pane action: buttons disabled meanwhile, errors in the banner. */
  async function act(action: () => Promise<unknown>, after?: () => void) {
    setBusy(true)
    setError(null)
    try {
      await action()
      after?.()
    } catch (err) {
      setError(messageOf(err)) // nothing changed; the pane keeps its state
    } finally {
      setBusy(false)
      reload() // list + counts: the email may have moved or left the view
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
          : `Classified ${totals.classified} email${totals.classified === 1 ? '' : 's'} by keywords.`,
      )
      announceUrgent(totals)
    } catch (err) {
      setError(messageOf(err))
    } finally {
      // Refresh even after an error: earlier requests may have saved results
      reload()
      setClassifying(false)
    }
  }

  /** Alert for new critical/high emails: in-page toast always, desktop notification if allowed. */
  function announceUrgent(counts: { critical: number; high: number }) {
    const message = alertMessage(counts)
    if (!message) return // nothing urgent: no alert
    const target = alertView(counts)
    const open = () => {
      setToast(null)
      selectView(target)
    }
    setToast({ message, actionLabel: `Show ${target}`, onAction: open })
    notify('New urgent emails', message, open)
  }

  function handleDelete(email: Email) {
    // Reversible, so no "are you sure?": act at once and offer Undo
    void act(
      () => deleteEmail(email.id),
      () =>
        setToast({
          message: 'Email moved to Trash.',
          actionLabel: 'Undo',
          onAction: () => {
            setToast(null)
            void act(() => restoreEmail(email.id))
          },
        }),
    )
  }

  function handleEmptyTrash() {
    setConfirmEmpty(false)
    void act(async () => {
      const { deleted } = await emptyTrash()
      setSelectedId(null)
      setToast({ message: `Permanently deleted ${deleted} email${deleted === 1 ? '' : 's'}.` })
    })
  }

  // Status line under the toolbar: progress, result of the last action, or a hint
  const statusText = classifying
    ? `Classifying… ${progress} of ${target}`
    : (notice ?? `${unclassified} unclassified`)

  // App shell: the page itself never scrolls (h-screen); only the list and the
  // pane do. min-h-0 / min-w-0 let flex children shrink so overflow-y-auto works.
  // Wide screens (xl): list and pane side by side. Narrower: the pane replaces
  // the list while an email is open ("Back to list").
  return (
    <div className="flex h-screen flex-col bg-gray-50">
      <Toolbar classifying={classifying} loadingList={loadingList} onClassify={handleClassify} />
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
        {/* `relative` matters: rows contain screen-reader-only text (sr-only =
            position: absolute). A scroll container only clips absolutely positioned
            children if it is itself positioned; without it they stuck out below the
            page and made the WHOLE page scroll into a long blank area (#66). */}
        <main
          data-testid="list-scroll"
          className={`relative min-w-0 flex-1 overflow-y-auto bg-white ${selected ? 'hidden xl:block' : ''}`}
        >
          <ViewSelect active={view} summary={summary} onSelect={selectView} />
          <EmailList
            emails={emails}
            loading={loadingList}
            emptyText={current.empty}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onEmptyTrash={inTrash ? () => setConfirmEmpty(true) : undefined}
          />
        </main>
        {selected && (
          <aside className="relative min-w-0 flex-1 overflow-y-auto border-l border-gray-200 bg-white xl:w-[45%] xl:flex-none">
            <ReadingPane
              email={selected}
              inTrash={inTrash}
              busy={busy}
              onPriorityChange={(priority: Priority) => void act(() => updateEmail(selected.id, { priority }))}
              onToggleHandled={() =>
                void act(() =>
                  updateEmail(selected.id, { status: selected.status === 'handled' ? 'new' : 'handled' }),
                )
              }
              onReclassify={() => void act(() => classifyOne(selected.id))}
              onDelete={() => handleDelete(selected)}
              onRestore={() => void act(() => restoreEmail(selected.id))}
              onClose={() => setSelectedId(null)}
            />
          </aside>
        )}
      </div>
      {confirmEmpty && (
        <ConfirmDialog
          title="Empty the Trash?"
          message={`Permanently delete ${summary?.trash ?? 0} email${summary?.trash === 1 ? '' : 's'}? This can't be undone.`}
          confirmLabel="Delete forever"
          onConfirm={handleEmptyTrash}
          onCancel={() => setConfirmEmpty(false)}
        />
      )}
      {toast && (
        <Toast message={toast.message} actionLabel={toast.actionLabel} onAction={toast.onAction} onDismiss={closeToast} />
      )}
    </div>
  )
}

export default App
