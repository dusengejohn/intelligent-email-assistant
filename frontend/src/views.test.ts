// The view table and the URL <-> view mapping (pure, Node environment).
import { describe, expect, it } from 'vitest'
import { VIEWS, viewById, viewFromUrl, viewUrl } from './views'

describe('VIEWS', () => {
  it('lists the nine sidebar views in order, the Plan first', () => {
    expect(VIEWS.map((v) => v.id)).toEqual([
      'plan',
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

  it('gives every email view a label, an empty message and a summary count', () => {
    for (const view of VIEWS.filter((v) => v.id !== 'plan')) {
      expect(view.label).not.toBe('')
      expect(view.empty).not.toBe('')
      expect(view.countKey).toBeTruthy()
    }
  })

  it('gives the Plan view no count; it loads all emails (for the reading pane)', () => {
    expect(viewById('plan').countKey).toBeUndefined()
    expect(viewById('plan').filter).toEqual({})
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
    ['?view=plan', 'plan'],
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
