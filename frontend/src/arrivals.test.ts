// Tests for new-mail detection (story 3b.5). Emails arrive from the generator
// through the ingest API; the inbox notices them from the /summary counts.
import { describe, expect, it } from 'vitest'
import type { EmailSummary } from './api'
import { arrivalMessage, arrived, POLL_INTERVAL_MS } from './arrivals'

function summary(all: number, trash = 0): EmailSummary {
  return {
    all,
    unclassified: 0,
    classified: all,
    critical: 0,
    high: 0,
    moderate: 0,
    low: all,
    handled: 0,
    trash,
  }
}

describe('arrived', () => {
  it('counts new emails', () => {
    expect(arrived(summary(152), summary(162))).toBe(10)
  })

  it('is 0 on the first load (nothing to compare with)', () => {
    expect(arrived(null, summary(162))).toBe(0)
  })

  it('is 0 when nothing changed', () => {
    expect(arrived(summary(5, 1), summary(5, 1))).toBe(0)
  })

  it('is 0 after a delete: the email only moved to the Trash', () => {
    expect(arrived(summary(10, 0), summary(9, 1))).toBe(0)
  })

  it('is 0 after a restore (e.g. Undo): the email only came back from the Trash', () => {
    expect(arrived(summary(9, 1), summary(10, 0))).toBe(0)
  })

  it('is 0 after emptying the Trash (never negative)', () => {
    expect(arrived(summary(9, 3), summary(9, 0))).toBe(0)
  })

  it('counts arrivals next to a delete in the same interval', () => {
    expect(arrived(summary(10, 0), summary(19, 1))).toBe(10)
  })
})

describe('arrivalMessage', () => {
  it.each([
    [1, '1 new email arrived'],
    [10, '10 new emails arrived'],
  ])('%i -> %j', (count, text) => {
    expect(arrivalMessage(count)).toBe(text)
  })
})

it('polls every 15 seconds', () => {
  expect(POLL_INTERVAL_MS).toBe(15_000)
})
