import { useEffect, useState } from 'react'
import { ApiError, getPlanning, type Plan, type PlanEmail } from '../api'
import { addDays, dayLabel, lanes, planSummary, position, timeIn } from '../plan'
import { PRIORITIES } from '../priorities'

interface Props {
  /** Bumped by the app after every change (new mail, Classify, handled...): reload */
  reloadKey: number
  /** The email open in the reading pane, highlighted here too */
  selectedId: number | null
  onOpen: (id: number) => void
}

const WAITING_SHOWN = 10 // the "doesn't fit today" list can be long (200+)

/** One item on the timeline: a meeting or a suggested reply block. */
interface Item {
  key: string
  kind: 'meeting' | 'reply'
  start: string
  end: string
  label: string
  color?: string
  emails: PlanEmail[]
}

/**
 * The Plan view (story 4.5): the day as a timeline (meetings in grey, suggested
 * reply blocks in their priority color), the plan in one sentence, a date switch,
 * and the emails that don't fit today. Advice only: it reads, never books.
 */
export function PlanView({ reloadKey, selectedId, onOpen }: Props) {
  const [day, setDay] = useState<string | undefined>(undefined) // undefined = today
  const [plan, setPlan] = useState<Plan | null>(null)
  const [today, setToday] = useState<string | null>(null) // learnt from the server
  const [error, setError] = useState<string | null>(null)
  const [showAllWaiting, setShowAllWaiting] = useState(false)

  useEffect(() => {
    let cancelled = false
    getPlanning(day)
      .then((result) => {
        if (cancelled) return
        setPlan(result)
        setError(null)
        if (day === undefined) setToday(result.date) // the server knows "today" in its zone
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load the plan.')
      })
    return () => {
      cancelled = true
    }
  }, [day, reloadKey])

  if (!plan) {
    return error ? <ErrorText message={error} /> : <p className="p-6 text-sm text-gray-500">Loading the plan…</p>
  }

  const tz = plan.timezone
  const onToday = today !== null && plan.date <= today
  const goTo = (next: string) => {
    setShowAllWaiting(false)
    setDay(next === today ? undefined : next)
  }
  const waiting = showAllWaiting ? plan.not_today : plan.not_today.slice(0, WAITING_SHOWN)

  return (
    <section aria-labelledby="plan-heading" className="flex flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h2 id="plan-heading" className="mr-auto text-lg font-semibold text-gray-900">
          Plan for {dayLabel(plan.date)}
        </h2>
        <button type="button" aria-label="Previous day" disabled={onToday} onClick={() => goTo(addDays(plan.date, -1))} className={NAV}>
          ‹
        </button>
        <button type="button" onClick={() => goTo(today ?? plan.date)} disabled={day === undefined} className={NAV}>
          Today
        </button>
        <button type="button" aria-label="Next day" onClick={() => goTo(addDays(plan.date, 1))} className={NAV}>
          ›
        </button>
      </header>

      {error && <ErrorText message={error} />}
      <p className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-900">{planSummary(plan)}</p>
      <p className="text-xs text-gray-500">Advice only: nothing is booked in your calendar. Times in {tz}.</p>

      {plan.window && <Timeline plan={plan} window={plan.window} selectedId={selectedId} onOpen={onOpen} />}

      {plan.not_today.length > 0 && (
        <section aria-label={'Doesn’t fit today'} className="rounded-md border border-gray-200 p-3">
          <h3 className="text-sm font-semibold text-gray-700">
            Doesn’t fit today ({plan.not_today.length})
          </h3>
          <ul className="mt-2 flex flex-col gap-1">
            {waiting.map((email) => (
              <li key={email.id}>
                <EmailButton email={email} selected={email.id === selectedId} onOpen={onOpen} showPriority />
              </li>
            ))}
          </ul>
          {plan.not_today.length > WAITING_SHOWN && (
            <button type="button" onClick={() => setShowAllWaiting(!showAllWaiting)} className="mt-2 text-sm text-blue-700 hover:underline">
              {showAllWaiting ? 'Show fewer' : `Show all ${plan.not_today.length}`}
            </button>
          )}
        </section>
      )}
    </section>
  )
}

const NAV =
  'rounded-md border border-gray-300 px-2.5 py-1 text-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40'

function ErrorText({ message }: { message: string }) {
  return (
    <p role="alert" className="m-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  )
}

function Timeline({
  plan,
  window,
  selectedId,
  onOpen,
}: {
  plan: Plan
  window: { start: string; end: string }
  selectedId: number | null
  onOpen: (id: number) => void
}) {
  const tz = plan.timezone
  const items: Item[] = [
    ...plan.events.map((event) => ({
      key: `event-${event.id}`,
      kind: 'meeting' as const,
      start: event.start,
      end: event.end,
      label: `Meeting: ${event.title}`,
      emails: [],
    })),
    ...plan.suggestions.map((block) => ({
      key: `reply-${block.start}`,
      kind: 'reply' as const,
      start: block.start,
      end: block.end,
      label: `${PRIORITIES[block.priority].label}: ${block.emails.length} email${block.emails.length === 1 ? '' : 's'}`,
      color: PRIORITIES[block.priority].color,
      emails: block.emails,
    })),
  ]
    .filter((item) => position(item.start, item.end, window) !== null) // e.g. an 08:00 call
    .sort((a, b) => a.start.localeCompare(b.start))
  const placement = lanes(items)

  // A line and a label for every hour of the working day
  const hours: string[] = []
  for (let t = Date.parse(window.start); t < Date.parse(window.end); t += 3_600_000) {
    hours.push(new Date(t).toISOString())
  }

  return (
    <div className="relative ml-12 h-[40rem] border-l border-gray-200">
      {hours.map((hour) => (
        <div key={hour} aria-hidden="true" className="absolute right-0 left-0 border-t border-gray-100" style={{ top: `${position(hour, window.end, window)!.top}%` }}>
          <span className="absolute -left-12 -translate-y-1/2 text-xs text-gray-400">{timeIn(hour, tz)}</span>
        </div>
      ))}
      <ol aria-label="Timeline" className="absolute inset-0">
        {items.map((item, i) => {
          const place = position(item.start, item.end, window)!
          const { lane, of } = placement[i]
          const time = `${timeIn(item.start, tz)}–${timeIn(item.end, tz)}`
          return (
            <li
              key={item.key}
              aria-label={`${time} ${item.label}`}
              data-kind={item.kind}
              className={`absolute overflow-hidden rounded-md px-2 py-0.5 text-xs ${
                item.kind === 'meeting' ? 'bg-gray-200 text-gray-700' : 'border-l-4 bg-white text-gray-900 shadow-sm ring-1 ring-gray-200'
              }`}
              style={{
                top: `${place.top}%`,
                height: `${place.height}%`,
                left: `calc(${(lane / of) * 100}% + 0.25rem)`,
                width: `calc(${100 / of}% - 0.5rem)`,
                borderLeftColor: item.color,
              }}
            >
              <span className="mr-2 font-medium text-gray-500">{time}</span>
              {item.kind === 'meeting' ? (
                <span>{item.label.replace('Meeting: ', '')}</span>
              ) : (
                <ul className="inline">
                  {item.emails.map((email) => (
                    <li key={email.id} className="inline">
                      <EmailButton email={email} selected={email.id === selectedId} onOpen={onOpen} />
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function EmailButton({
  email,
  selected,
  onOpen,
  showPriority = false,
}: {
  email: PlanEmail
  selected: boolean
  onOpen: (id: number) => void
  showPriority?: boolean
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(email.id)}
      aria-current={selected ? 'true' : undefined}
      className={`mr-2 text-left hover:underline ${selected ? 'font-semibold text-blue-800' : ''}`}
    >
      {showPriority && (
        <span aria-hidden="true" className="mr-1.5 inline-block size-2 rounded-full" style={{ backgroundColor: PRIORITIES[email.priority].color }} />
      )}
      {email.subject} · {email.minutes} min
    </button>
  )
}
