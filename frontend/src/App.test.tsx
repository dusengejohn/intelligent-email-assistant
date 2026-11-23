// @vitest-environment jsdom
// The whole page against a small in-memory fake backend: views, reading pane,
// delete/undo/restore, empty trash, and the requests the page sends.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Email, EmailSummary } from './api'

function email(id: number, subject: string, priority: Email['priority']): Email {
  return {
    id,
    sender_name: `Sender ${id}`,
    sender_email: `s${id}@example.com`,
    subject,
    body: `Body of ${subject}.\nSecond line.`,
    received_at: '2026-11-21T15:00:00Z',
    priority,
    priority_reason: priority ? 'Reason.' : null,
    classification_source: priority ? 'ai' : null,
    suggested_response_minutes: priority ? 15 : null,
    status: 'new',
    created_at: '2026-11-21T15:00:00Z',
    deleted_at: null,
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** In-memory backend: lists, summary, PATCH, delete/restore/empty trash. Records requests. */
function fakeApi(initial: Email[]) {
  const db = initial.map((e) => ({ ...e }))
  const requests: string[] = []
  const active = () => db.filter((e) => !e.deleted_at)
  const summary = (): EmailSummary => {
    const list = active()
    const count = (p: Email['priority']) => list.filter((e) => e.priority === p).length
    return {
      all: list.length,
      unclassified: count(null),
      classified: list.length - count(null),
      critical: count('critical'),
      high: count('high'),
      moderate: count('moderate'),
      low: count('low'),
      handled: list.filter((e) => e.status === 'handled').length,
      trash: db.length - list.length,
    }
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      requests.push(method === 'GET' ? path : `${method} ${path}`)
      const id = Number(path.match(/\/api\/emails\/(\d+)/)?.[1])
      const target = db.find((e) => e.id === id)
      if (path === '/api/health') return json({ status: 'ok' })
      if (path === '/api/emails/summary') return json(summary())
      if (method === 'DELETE' && path === '/api/emails/trash') {
        const before = db.length
        db.splice(0, db.length, ...active())
        return json({ deleted: before - db.length })
      }
      if (method === 'DELETE' && target) {
        target.deleted_at = '2026-11-23T10:00:00Z'
        return new Response(null, { status: 204 })
      }
      if (method === 'POST' && path.endsWith('/restore') && target) {
        target.deleted_at = null
        return json(target)
      }
      if (method === 'PATCH' && target) {
        Object.assign(target, JSON.parse(init?.body as string))
        return json(target)
      }
      if (path.startsWith('/api/emails')) {
        const params = new URLSearchParams(path.split('?')[1] ?? '')
        let list = params.get('trash') ? db.filter((e) => e.deleted_at) : active()
        const priority = params.get('priority')
        if (priority) list = list.filter((e) => e.priority === priority)
        if (params.get('classified') === 'false') list = list.filter((e) => !e.priority)
        if (params.get('classified') === 'true') list = list.filter((e) => e.priority)
        return json(list)
      }
      return json({ detail: 'Not Found' }, 404)
    }),
  )
  return { requests, db }
}

function list() {
  return screen.getByRole('list', { name: 'Emails' })
}

function subjects(): string[] {
  return within(list())
    .getAllByRole('listitem')
    .map((item) => within(item).getByTestId('subject').textContent ?? '')
}

async function openRow(subject: string) {
  await userEvent.click(within(list()).getByRole('button', { name: new RegExp(subject) }))
}

beforeEach(() => {
  window.history.replaceState(null, '', '/')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App: list and views', () => {
  it('lists the emails in the order the API returns them', async () => {
    // Deliberately not sorted by priority: the browser must not re-sort
    fakeApi([email(3, 'Third', 'low'), email(1, 'First', 'critical'), email(2, 'Second', null)])

    render(<App />)

    await screen.findByRole('list', { name: 'Emails' })
    expect(subjects()).toEqual(['Third', 'First', 'Second'])
  })

  it('shows the toolbar and the view counts from the summary', async () => {
    fakeApi([email(1, 'One', 'high'), email(2, 'Two', null)])

    render(<App />)

    expect(screen.getByRole('button', { name: /Classify/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/Scenario/)).toBeInTheDocument()
    const views = screen.getByRole('navigation', { name: 'Views' })
    expect(await within(views).findByRole('button', { name: /All/ })).toHaveTextContent('2')
    expect(within(views).getByRole('button', { name: /Unclassified/ })).toHaveTextContent('1')
  })

  it('opens the view named in the URL', async () => {
    window.history.replaceState(null, '', '/?view=critical')
    const { requests } = fakeApi([email(1, 'One', 'critical')])

    render(<App />)

    await screen.findByRole('list', { name: 'Emails' })
    expect(requests).toContain('/api/emails?priority=critical')
  })

  it('loads the right emails and updates the URL when a view is clicked', async () => {
    const { requests } = fakeApi([email(1, 'One', null)])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })

    await userEvent.click(screen.getByRole('button', { name: /Unclassified/ }))

    await waitFor(() => expect(requests).toContain('/api/emails?classified=false'))
    expect(window.location.search).toBe('?view=unclassified')
  })

  it('goes back to the previous view with the browser Back button', async () => {
    fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    const views = screen.getByRole('navigation', { name: 'Views' })
    await userEvent.click(within(views).getByRole('button', { name: /Low/ }))
    await waitFor(() => expect(window.location.search).toBe('?view=low'))

    window.history.back()

    await waitFor(() =>
      expect(within(views).getByRole('button', { name: /^All/ })).toHaveAttribute('aria-current', 'page'),
    )
  })

  it('shows the empty message of the current view', async () => {
    window.history.replaceState(null, '', '/?view=unclassified')
    fakeApi([])

    render(<App />)

    expect(await screen.findByText('Nothing to classify.')).toBeInTheDocument()
  })

  it('keeps hidden screen-reader labels inside the scrolling list', async () => {
    // Regression (#66): without `relative`, sr-only (position: absolute) labels
    // escaped the scroll area and the whole page scrolled into blank space
    fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })

    expect(screen.getByTestId('list-scroll')).toHaveClass('relative', 'overflow-y-auto')
  })
})

describe('App: reading pane', () => {
  it('opens the full email when a row is clicked', async () => {
    fakeApi([email(1, 'One', 'low'), email(2, 'Two', 'high')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })

    await openRow('Two')

    const pane = screen.getByRole('region', { name: 'Reading pane' })
    expect(within(pane).getByRole('heading', { name: 'Two' })).toBeInTheDocument()
    expect(within(pane).getByTestId('email-body').textContent).toBe('Body of Two.\nSecond line.')
    expect(within(list()).getByRole('button', { name: /Two/ })).toHaveAttribute('aria-current', 'true')
  })

  it('changes the priority and reloads the list and counts', async () => {
    const { requests } = fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    await openRow('One')
    const summaryCalls = () => requests.filter((r) => r === '/api/emails/summary').length
    const before = summaryCalls()

    await userEvent.selectOptions(screen.getByLabelText('Change priority'), 'high')

    await waitFor(() => expect(summaryCalls()).toBe(before + 1))
    expect(requests).toContain('PATCH /api/emails/1')
  })

  it('marks an email handled', async () => {
    const { requests } = fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    await openRow('One')

    await userEvent.click(screen.getByRole('button', { name: 'Mark handled' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Mark as new' })).toBeInTheDocument())
    expect(requests).toContain('PATCH /api/emails/1')
  })

  it('deletes to the Trash, selects the next email, and Undo restores it', async () => {
    const { requests } = fakeApi([email(1, 'One', 'low'), email(2, 'Two', 'low'), email(3, 'Three', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    await openRow('Two')

    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(subjects()).toEqual(['One', 'Three']))
    expect(requests).toContain('DELETE /api/emails/2')
    // the email below the deleted one is now open
    const pane = screen.getByRole('region', { name: 'Reading pane' })
    expect(within(pane).getByRole('heading', { name: 'Three' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))

    await waitFor(() => expect(subjects()).toEqual(['One', 'Two', 'Three']))
    expect(requests).toContain('POST /api/emails/2/restore')
  })

  it('restores from the Trash view', async () => {
    window.history.replaceState(null, '', '/?view=trash')
    const { requests } = fakeApi([{ ...email(5, 'Deleted', 'low'), deleted_at: '2026-11-23T10:00:00Z' }])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    await openRow('Deleted')

    expect(screen.queryByLabelText('Change priority')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))

    await waitFor(() => expect(requests).toContain('POST /api/emails/5/restore'))
    expect(await screen.findByText('Trash is empty.')).toBeInTheDocument()
  })

  it('empties the Trash only after confirmation', async () => {
    window.history.replaceState(null, '', '/?view=trash')
    const { requests } = fakeApi([{ ...email(5, 'Deleted', 'low'), deleted_at: '2026-11-23T10:00:00Z' }])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })

    await userEvent.click(screen.getByRole('button', { name: /Empty trash/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(requests).not.toContain('DELETE /api/emails/trash')

    await userEvent.click(screen.getByRole('button', { name: /Empty trash/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete forever' }))

    await waitFor(() => expect(requests).toContain('DELETE /api/emails/trash'))
    expect(await screen.findByText('Trash is empty.')).toBeInTheDocument()
  })
})
