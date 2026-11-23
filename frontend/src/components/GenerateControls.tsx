import { useState, type FormEvent } from 'react'

export const MIN_COUNT = 1
export const MAX_COUNT = 50

interface Props {
  generating: boolean
  /** Another action (e.g. Classify) is running: block generating meanwhile */
  disabled?: boolean
  onGenerate: (count: number, scenario: string) => void
}

/** Number + optional scenario + "Generate emails" button. */
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
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:flex-row sm:items-end"
    >
      <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
        How many
        <input
          type="number"
          min={MIN_COUNT}
          max={MAX_COUNT}
          step={1}
          required
          value={count}
          onChange={(e) => setCount(e.target.value)}
          disabled={generating}
          className="w-24 rounded-md border border-gray-300 px-2 py-1.5 invalid:border-red-500"
        />
      </label>
      <label className="flex flex-1 flex-col gap-1 text-sm font-medium text-gray-700">
        Scenario (optional)
        <input
          type="text"
          maxLength={200}
          placeholder="e.g. IT infrastructure team"
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          disabled={generating}
          className="rounded-md border border-gray-300 px-2 py-1.5"
        />
      </label>
      <button
        type="submit"
        disabled={generating || disabled || !valid}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {generating ? 'Generating…' : 'Generate emails'}
      </button>
    </form>
  )
}
