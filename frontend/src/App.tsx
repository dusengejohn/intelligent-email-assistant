import { useEffect, useState } from 'react'
import { ApiError, generateEmails, listEmails, type Email } from './api'
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
  const [error, setError] = useState<string | null>(null)

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
    try {
      await generateEmails(count, scenario)
      setEmails(await listEmails()) // refresh: show the new emails in list order
    } catch (err) {
      setError(messageOf(err)) // the existing list stays as it was
    } finally {
      setGenerating(false)
    }
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-gray-900">Intelligent Email Assistant</h1>
        <HealthPill />
      </header>

      <section className="flex flex-col gap-2">
        <GenerateControls generating={generating} onGenerate={handleGenerate} />
        {generating && (
          <p className="text-sm text-gray-500">
            Claude is writing your emails. This can take 15 seconds or more…
          </p>
        )}
      </section>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Emails {!loadingList && <span className="text-gray-500">({emails.length})</span>}
        </h2>
        <EmailList emails={emails} loading={loadingList} />
      </section>
    </main>
  )
}

export default App
