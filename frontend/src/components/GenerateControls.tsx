import { useState, type FormEvent } from 'react'

export const MIN_COUNT = 1
export const MAX_COUNT = 50

interface Props {
  generating: boolean
  /** Another action (e.g. Classify) is running: block generating meanwhile */
  disabled?: boolean
  onGenerate: (count: number, scenario: string) => void
}

/** Compact toolbar form: count, optional scenario, "Generate emails" (one aligned row). */
export function GenerateControls({ generating, disabled = false, onGenerate }: Props) {
  // Kept as text while typing, so the field can be briefly empty
  const [count, setCount] = useState('10')
  const [scenario, setScenario] = useState('')

  const value = Number(count)
  const valid = Number.isInteger(value) && value >= MIN_COUNT && value <= MAX_COUNT

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault() // stay on the page (no full-page form submit)
    if (valid && !generating && !disabled) onGenerate(value, scenario)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-1 text-sm text-gray-700">
        <span className="sr-only">How many emails</span>
        <input
          type="number"
          min={MIN_COUNT}
          max={MAX_COUNT}
          step={1}
          required
          value={count}
          onChange={(e) => setCount(e.target.value)}
          disabled={generating}
          className="w-16 rounded-md border border-gray-300 px-2 py-1 invalid:border-red-500"
        />
      </label>
      {/* Always visible, fixed width, same height as the count field (was a toggle) */}
      <label className="text-sm text-gray-700">
        <span className="sr-only">Scenario (optional)</span>
        <input
          type="text"
          maxLength={200}
          placeholder="Scenario (optional), e.g. IT team"
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          disabled={generating}
          className="w-64 rounded-md border border-gray-300 px-2 py-1 placeholder:text-gray-400"
        />
      </label>
      <button
        type="submit"
        disabled={generating || disabled || !valid}
        className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {generating ? 'Generating…' : 'Generate emails'}
      </button>
    </form>
  )
}
