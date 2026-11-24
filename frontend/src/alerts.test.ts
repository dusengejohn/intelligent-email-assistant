// Alert text and target view for new urgent emails (pure).
import { describe, expect, it } from 'vitest'
import { alertMessage, alertView } from './alerts'

describe('alertMessage', () => {
  it.each([
    [{ critical: 2, high: 3 }, '2 new critical, 3 new high'],
    [{ critical: 1, high: 0 }, '1 new critical'],
    [{ critical: 0, high: 1 }, '1 new high'],
  ])('describes %j', (counts, text) => {
    expect(alertMessage(counts)).toBe(text)
  })

  it('has nothing to say when nothing urgent is new', () => {
    expect(alertMessage({ critical: 0, high: 0 })).toBeNull()
  })
})

describe('alertView', () => {
  it('opens Critical when there are new critical emails, else High', () => {
    expect(alertView({ critical: 1, high: 5 })).toBe('critical')
    expect(alertView({ critical: 0, high: 5 })).toBe('high')
  })
})
