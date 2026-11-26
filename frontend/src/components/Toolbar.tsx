import { DesktopAlertsButton } from './DesktopAlertsButton'
import { HealthPill } from './HealthPill'

// Where new emails come from (story 3b.5): the separate Email Generator app.
// Written into the page at build time (VITE_GENERATOR_URL); the Docker default port.
const GENERATOR_URL: string = import.meta.env.VITE_GENERATOR_URL ?? 'http://localhost:8081'

interface Props {
  classifying: boolean
  loadingList: boolean
  onClassify: () => void
}

/** The top bar: always visible, the list scrolls underneath. */
export function Toolbar({ classifying, loadingList, onClassify }: Props) {
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-gray-200 bg-white px-4 py-2">
      <h1 className="text-lg font-bold text-gray-900">Intelligent Email Assistant</h1>
      <button
        type="button"
        onClick={onClassify}
        disabled={classifying || loadingList}
        className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {classifying ? 'Classifying…' : 'Classify'}
      </button>
      <p className="text-sm text-gray-500">
        New emails come from the{' '}
        <a href={GENERATOR_URL} className="text-blue-600 underline hover:text-blue-800">
          Email Generator
        </a>
      </p>
      <div className="ml-auto flex items-center gap-3">
        <DesktopAlertsButton />
        <HealthPill />
      </div>
    </header>
  )
}
