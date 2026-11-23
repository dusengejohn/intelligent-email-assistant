import { GenerateControls } from './GenerateControls'
import { HealthPill } from './HealthPill'

interface Props {
  generating: boolean
  classifying: boolean
  loadingList: boolean
  onGenerate: (count: number, scenario: string) => void
  onClassify: () => void
}

/** The top bar: always visible, the list scrolls underneath. */
export function Toolbar({ generating, classifying, loadingList, onGenerate, onClassify }: Props) {
  // Generate and Classify both change the list: never run them at the same time
  const busy = generating || classifying
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-gray-200 bg-white px-4 py-2">
      <h1 className="text-lg font-bold text-gray-900">Intelligent Email Assistant</h1>
      <div className="flex flex-wrap items-center gap-2">
        <GenerateControls generating={generating} disabled={classifying} onGenerate={onGenerate} />
        <button
          type="button"
          onClick={onClassify}
          disabled={busy || loadingList}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {classifying ? 'Classifying…' : 'Classify'}
        </button>
      </div>
      <div className="ml-auto">
        <HealthPill />
      </div>
    </header>
  )
}
