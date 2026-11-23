// Pure formatting helpers: no browser needed (default Node environment).
import { describe, expect, it } from 'vitest'
import { listDate, snippet } from './format'

describe('listDate', () => {
  // Times chosen far from midnight, so the result doesn't depend on the timezone
  const now = new Date('2026-11-23T15:00:00Z')

  it('shows only the time for an email from today', () => {
    expect(listDate('2026-11-23T14:05:00Z', now, 'en-US')).toMatch(/^\d{1,2}:\d{2}/)
  })

  it('shows month and day for an earlier day this year', () => {
    expect(listDate('2026-11-21T15:00:00Z', now, 'en-US')).toBe('Nov 21')
  })

  it('adds the year for an email from another year', () => {
    expect(listDate('2025-11-21T15:00:00Z', now, 'en-US')).toBe('Nov 21, 2025')
  })
})

describe('snippet', () => {
  it('joins lines into one', () => {
    expect(snippet('Hi team,\n\nThe database is down.\nPriya')).toBe(
      'Hi team, The database is down. Priya',
    )
  })

  it('cuts long text with an ellipsis', () => {
    const result = snippet('word '.repeat(100))
    expect(result.length).toBeLessThanOrEqual(140)
    expect(result.endsWith('…')).toBe(true)
  })

  it('leaves short text unchanged', () => {
    expect(snippet('Short body.')).toBe('Short body.')
  })
})
