// Which email to select after the selected one leaves the view (pure).
import { describe, expect, it } from 'vitest'
import { nextSelection } from './selection'

describe('nextSelection', () => {
  it('picks the email below the removed one', () => {
    expect(nextSelection([1, 2, 3], 2)).toBe(3)
  })

  it('picks the one above when the last email was removed', () => {
    expect(nextSelection([1, 2, 3], 3)).toBe(2)
  })

  it('picks nothing when the only email was removed', () => {
    expect(nextSelection([5], 5)).toBeNull()
  })

  it('falls back to the first email when the removed id is unknown', () => {
    expect(nextSelection([4, 5], 99)).toBe(4)
  })

  it('picks nothing for an empty list', () => {
    expect(nextSelection([], 1)).toBeNull()
  })
})
