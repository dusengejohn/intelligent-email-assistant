// Pure helpers for the Plan view (story 4.5): the summary sentence, times in the
// app's time zone, positions on the timeline, overlap lanes and date steps.
// Node environment: no DOM needed.
import { describe, expect, it } from 'vitest'
import type { Plan, PlanBlock, PlanEmail, Priority } from './api'
import { addDays, lanes, planSummary, position, timeIn } from './plan'

const TZ = 'America/Toronto'
// Thursday 2026-11-26: 09:00-17:00 in Toronto = 14:00-22:00 UTC
const WINDOW = { start: '2026-11-26T14:00:00Z', end: '2026-11-26T22:00:00Z' }

function email(id: number, priority: Priority, minutes = 15): PlanEmail {
  return { id, subject: `Email ${id}`, priority, minutes }
}

function block(start: string, end: string, priority: Priority, count = 1): PlanBlock {
  const emails = Array.from({ length: count }, (_, i) => email(i + 1, priority))
  return { start: `2026-11-26T${start}:00Z`, end: `2026-11-26T${end}:00Z`, priority, emails }
}

function plan(overrides: Partial<Plan> = {}): Plan {
  return {
    date: '2026-11-26',
    timezone: TZ,
    window: WINDOW,
    events: [],
    free_slots: [],
    suggestions: [],
    not_today: [],
    unclassified: 0,
    ...overrides,
  }
}

describe('timeIn', () => {
  it('shows a UTC instant in the app time zone, 24 h', () => {
    expect(timeIn('2026-11-26T14:00:00Z', TZ)).toBe('09:00')
    expect(timeIn('2026-11-26T21:45:00Z', TZ)).toBe('16:45')
    expect(timeIn('2026-07-15T13:30:00Z', TZ)).toBe('09:30') // summer: UTC-4
  })

  it('follows the zone it is given, not the computer running it', () => {
    expect(timeIn('2026-11-26T14:00:00Z', 'Europe/Berlin')).toBe('15:00')
  })
})

describe('position', () => {
  it('places an item by percentage of the working day', () => {
    // 09:00-10:00 in a 8-hour day: top 0 %, height 12.5 %
    expect(position('2026-11-26T14:00:00Z', '2026-11-26T15:00:00Z', WINDOW)).toEqual({ top: 0, height: 12.5 })
    // 13:00-17:00: the second half
    expect(position('2026-11-26T18:00:00Z', '2026-11-26T22:00:00Z', WINDOW)).toEqual({ top: 50, height: 50 })
  })

  it('cuts items at the edges of the day', () => {
    // The team social 16:30-17:30 is drawn until 17:00 only
    expect(position('2026-11-26T21:30:00Z', '2026-11-26T22:30:00Z', WINDOW)).toEqual({ top: 93.75, height: 6.25 })
    // An early call 08:00-08:45 is outside the day
    expect(position('2026-11-26T13:00:00Z', '2026-11-26T13:45:00Z', WINDOW)).toBeNull()
  })
})

describe('lanes', () => {
  it('puts overlapping items side by side and the others full width', () => {
    const items = [
      { start: '2026-11-26T14:30:00Z', end: '2026-11-26T14:45:00Z' }, // stand-up
      { start: '2026-11-26T18:00:00Z', end: '2026-11-26T21:00:00Z' }, // workshop
      { start: '2026-11-26T20:30:00Z', end: '2026-11-26T21:00:00Z' }, // 1:1 inside it
    ]

    expect(lanes(items)).toEqual([
      { lane: 0, of: 1 },
      { lane: 0, of: 2 },
      { lane: 1, of: 2 },
    ])
  })

  it('gives an item right after an overlap the full width again (Thursday at 16:00)', () => {
    const items = [
      { start: '2026-11-26T18:00:00Z', end: '2026-11-26T21:00:00Z' }, // workshop 13:00-16:00
      { start: '2026-11-26T20:30:00Z', end: '2026-11-26T21:00:00Z' }, // 1:1 15:30-16:00
      { start: '2026-11-26T21:00:00Z', end: '2026-11-26T21:20:00Z' }, // reply block at 16:00
    ]

    expect(lanes(items)).toEqual([
      { lane: 0, of: 2 },
      { lane: 1, of: 2 },
      { lane: 0, of: 1 },
    ])
  })

  it('treats touching items as not overlapping', () => {
    const items = [
      { start: '2026-11-26T17:00:00Z', end: '2026-11-26T18:00:00Z' }, // lunch
      { start: '2026-11-26T18:00:00Z', end: '2026-11-26T21:00:00Z' }, // workshop right after
    ]

    expect(lanes(items)).toEqual([
      { lane: 0, of: 1 },
      { lane: 0, of: 1 },
    ])
  })
})

describe('addDays', () => {
  it.each([
    ['2026-11-26', 1, '2026-11-27'],
    ['2026-11-30', 1, '2026-12-01'],
    ['2026-12-31', 1, '2027-01-01'],
    ['2026-03-01', -1, '2026-02-28'],
  ])('%s %+d -> %s', (day, n, expected) => {
    expect(addDays(day, n)).toBe(expected)
  })
})

describe('planSummary', () => {
  it('names what is planned, when, and what waits', () => {
    const summary = planSummary(
      plan({
        suggestions: [
          block('14:00', '14:20', 'critical'),
          block('14:20', '14:30', 'moderate'),
          block('14:45', '15:30', 'critical'),
          block('15:30', '16:00', 'high'),
          block('21:45', '22:00', 'low', 3),
        ],
        not_today: [email(9, 'moderate', 90), email(10, 'low')],
        unclassified: 5,
      }),
    )

    expect(summary).toBe(
      '2 critical, 1 high and 1 moderate emails planned from 09:00 to 11:00; ' +
        '3 low emails batched at 16:45; 2 don’t fit today; 5 unclassified (Classify first).',
    )
  })

  it('handles a day full of critical emails', () => {
    const suggestions = [block('14:00', '14:30', 'critical'), block('21:00', '21:30', 'critical')]
    const waiting = Array.from({ length: 207 }, (_, i) => email(100 + i, 'high'))

    expect(planSummary(plan({ suggestions, not_today: waiting }))).toBe(
      '2 critical emails planned from 09:00 to 16:30; 207 don’t fit today.',
    )
  })

  it('uses the singular for one of each', () => {
    const summary = planSummary(
      plan({
        suggestions: [block('14:00', '14:15', 'high'), block('21:55', '22:00', 'low')],
        not_today: [email(3, 'critical', 600)],
        unclassified: 1,
      }),
    )

    expect(summary).toBe(
      '1 high email planned from 09:00 to 09:15; 1 low email batched at 16:55; ' +
        '1 doesn’t fit today; 1 unclassified (Classify first).',
    )
  })

  it('says when there is nothing to plan', () => {
    expect(planSummary(plan())).toBe('Nothing to plan: no open, classified emails.')
    expect(planSummary(plan({ unclassified: 4 }))).toBe(
      'Nothing to plan: no open, classified emails; 4 unclassified (Classify first).',
    )
  })

  it('says when the working day is over', () => {
    const waiting = Array.from({ length: 219 }, (_, i) => email(i, 'moderate'))

    expect(planSummary(plan({ window: null, not_today: waiting }))).toBe(
      'The working day is over; 219 emails wait for another day.',
    )
    expect(planSummary(plan({ window: null }))).toBe('The working day is over.')
  })

  it('reports waiting emails even when none could be planned', () => {
    expect(planSummary(plan({ not_today: [email(1, 'critical', 600)] }))).toBe(
      '1 doesn’t fit today.',
    )
  })
})
