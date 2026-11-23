// The view table and the URL <-> view mapping (pure, Node environment).
import { describe, expect, it } from 'vitest'
import { VIEWS, viewById, viewFromUrl, viewUrl } from './views'

describe('VIEWS', () => {
  it('lists the eight sidebar views in order', () => {
    expect(VIEWS.map((v) => v.id)).toEqual([
      'all',
      'unclassified',
      'classified',
      'critical',
      'high',
      'moderate',
      'low',
      'trash',
    ])
  })

  it('gives every view a label, an empty message and a summary count', () => {
    for (const view of VIEWS) {
      expect(view.label).not.toBe('')
      expect(view.empty).not.toBe('')
      expect(view.countKey).toBeTruthy()
    }
  })

  it('maps views to API filters', () => {
    expect(viewById('all').filter).toEqual({})
    expect(viewById('unclassified').filter).toEqual({ classified: false })
    expect(viewById('critical').filter).toEqual({ priority: 'critical' })
    expect(viewById('trash').filter).toEqual({ trash: true })
  })
})

describe('view <-> URL', () => {
  it.each([
    ['?view=critical', 'critical'],
    ['?view=trash', 'trash'],
    ['?view=banana', 'all'],
    ['', 'all'],
  ])('reads %j as %s', (search, id) => {
    expect(viewFromUrl(search)).toBe(id)
  })

  it('writes a clean URL for "all" and ?view= for the others', () => {
    expect(viewUrl('all')).toBe('/')
    expect(viewUrl('trash')).toBe('/?view=trash')
  })
})
