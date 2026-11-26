// Pure helpers for the Plan view (story 4.5). No DOM, no clock: unit tested in Node.
import type { Plan, PlanBlock, Priority } from './api'
import { PRIORITIES, PRIORITY_ORDER } from './priorities'

/**
 * A UTC instant as "09:00" in the given IANA zone (the server's APP_TIMEZONE), so
 * the plan reads the same on every computer, whatever zone the browser is in.
 */
export function timeIn(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
  }).format(new Date(iso))
}

/** "2026-11-26" -> "Thursday, November 26" (a calendar date, no time zone involved). */
export function dayLabel(day: string): string {
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${day}T12:00:00Z`))
}

/** "2026-11-30" + 1 -> "2026-12-01" (calendar arithmetic on the date only). */
export function addDays(day: string, n: number): string {
  const date = new Date(`${day}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + n)
  return date.toISOString().slice(0, 10)
}

interface Span {
  start: string
  end: string
}

/**
 * Where an item sits on the timeline, in % of the working day: top = how far
 * into the day it starts, height = how long it lasts. Parts outside the day are
 * cut off; an item entirely outside it gets null (not drawn).
 */
export function position(start: string, end: string, window: Span): { top: number; height: number } | null {
  const dayStart = Date.parse(window.start)
  const dayLength = Date.parse(window.end) - dayStart
  const from = Math.max(Date.parse(start), dayStart)
  const to = Math.min(Date.parse(end), Date.parse(window.end))
  if (to <= from) return null
  return { top: ((from - dayStart) / dayLength) * 100, height: ((to - from) / dayLength) * 100 }
}

/**
 * Side-by-side lanes for overlapping items (e.g. a workshop and a 1:1 inside it).
 * Items are grouped into clusters of overlaps; within a cluster each item takes the
 * first free lane, and the whole cluster shares its width (`of` lanes). Items that
 * only touch don't overlap. `items` must be sorted by start; the result keeps order.
 */
export function lanes(items: Span[]): { lane: number; of: number }[] {
  const result: { lane: number; of: number }[] = []
  let cluster: number[] = [] // indexes of the current cluster
  let laneEnds: number[] = [] // when each lane of the cluster becomes free
  let clusterEnd = -Infinity

  const closeCluster = () => {
    for (const i of cluster) result[i].of = laneEnds.length
    cluster = []
    laneEnds = []
  }

  items.forEach((item, i) => {
    const start = Date.parse(item.start)
    const end = Date.parse(item.end)
    if (start >= clusterEnd) closeCluster() // no overlap with anything before
    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= start)
    if (lane === -1) lane = laneEnds.push(end) - 1
    else laneEnds[lane] = end
    result[i] = { lane, of: 1 }
    cluster.push(i)
    clusterEnd = Math.max(clusterEnd, end)
  })
  closeCluster()
  return result
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : pluralForm}`
}

/** "2 critical, 1 high and 1 moderate" */
function priorityCounts(blocks: PlanBlock[]): string {
  const counts = PRIORITY_ORDER.map((p) => [p, blocks.filter((b) => b.priority === p).length] as const)
  const parts = counts
    .filter(([, n]) => n > 0)
    .map(([p, n]) => `${n} ${PRIORITIES[p as Priority].label.toLowerCase()}`)
  return parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0]
}

/**
 * The plan in one sentence, built by code (no AI, ADR 0002): the same plan always
 * gives the same words, e.g. "2 critical and 1 high email planned from 09:00 to
 * 10:30; 3 low emails batched at 16:45; 2 don't fit today; 5 unclassified
 * (Classify first)."
 */
export function planSummary(plan: Plan): string {
  const tz = plan.timezone
  const parts: string[] = []
  const waiting = plan.not_today.length

  if (plan.window === null) {
    parts.push('The working day is over')
    if (waiting > 0) parts.push(`${plural(waiting, 'email')} wait for another day`)
  } else {
    const urgent = plan.suggestions.filter((b) => b.priority !== 'low')
    const lowBatch = plan.suggestions.find((b) => b.priority === 'low')
    if (urgent.length > 0) {
      const noun = urgent.length === 1 ? 'email' : 'emails'
      const from = timeIn(urgent[0].start, tz)
      const to = timeIn(urgent.reduce((last, b) => (b.end > last ? b.end : last), urgent[0].end), tz)
      parts.push(`${priorityCounts(urgent)} ${noun} planned from ${from} to ${to}`)
    }
    if (lowBatch) {
      parts.push(`${plural(lowBatch.emails.length, 'low email')} batched at ${timeIn(lowBatch.start, tz)}`)
    }
    if (waiting > 0) {
      parts.push(`${waiting} ${waiting === 1 ? 'doesn’t' : 'don’t'} fit today`)
    }
    if (parts.length === 0) parts.push('Nothing to plan: no open, classified emails')
  }
  if (plan.unclassified > 0) parts.push(`${plan.unclassified} unclassified (Classify first)`)
  return `${parts.join('; ')}.`
}
