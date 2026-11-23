// @vitest-environment jsdom
// The whole page with a fake API: layout, views in the URL, counts, refreshes.
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
    body: 'Body',
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

function summaryOf(emails: Email[]): EmailSummary {
  const count = (p: Email['priority']) => emails.filter((e) => e.priority === p).length
  return {
    all: emails.length,
    unclassified: count(null),
    classified: emails.length - count(null),
    critical: count('critical'),
    high: count('high'),
    moderate: count('moderate'),
    low: count('low'),
    handled: 0,
    trash: 0,
  }
}

/** Fake backend: answers health, summary, lists and PATCH; records every URL. */
function fakeApi(emails: Email[]) {
  const urls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init?: RequestInit) => {
      urls.push(init?.method ? `${init.method} ${path}` : path)
      let body: unknown = emails
      if (path === '/api/health') body = { status: 'ok' }
      else if (path === '/api/emails/summary') body = summaryOf(emails)
      else if (init?.method === 'PATCH') {
        const id = Number(path.split('/').pop())
        const changes = JSON.parse(init.body as string)
        body = { ...emails.find((e) => e.id === id), ...changes, classification_source: 'manual' }
      }
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
  return urls
}

function subjects(): string[] {
  const list = screen.getByRole('list', { name: 'Emails' })
  return within(list)
    .getAllByRole('listitem')
    .map((item) => within(item).getByTestId('subject').textContent ?? '')
}

beforeEach(() => {
  window.history.replaceState(null, '', '/')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
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
    expect(screen.getByRole('button', { name: /Generate/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/Scenario/)).toBeInTheDocument() // always visible now
    const views = screen.getByRole('navigation', { name: 'Views' })
    expect(await within(views).findByRole('button', { name: /All/ })).toHaveTextContent('2')
    expect(within(views).getByRole('button', { name: /Unclassified/ })).toHaveTextContent('1')
  })

  it('opens the view named in the URL', async () => {
    window.history.replaceState(null, '', '/?view=critical')
    const urls = fakeApi([email(1, 'One', 'critical')])

    render(<App />)

    await screen.findByRole('list', { name: 'Emails' })
    expect(urls).toContain('/api/emails?priority=critical')
    expect(screen.getByRole('button', { name: /Critical/ })).toHaveAttribute('aria-current', 'page')
  })

  it('loads the right emails and updates the URL when a view is clicked', async () => {
    const urls = fakeApi([email(1, 'One', null)])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })

    await userEvent.click(screen.getByRole('button', { name: /Unclassified/ }))

    await waitFor(() => expect(urls).toContain('/api/emails?classified=false'))
    expect(window.location.search).toBe('?view=unclassified')
  })

  it('goes back to the previous view with the browser Back button', async () => {
    const urls = fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    await userEvent.click(screen.getByRole('button', { name: /Low/ }))
    await waitFor(() => expect(window.location.search).toBe('?view=low'))

    window.history.back()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /All/ })).toHaveAttribute('aria-current', 'page'),
    )
    expect(urls.filter((u) => u === '/api/emails').length).toBeGreaterThanOrEqual(2)
  })

  it('shows the Trash read-only (no priority dropdown)', async () => {
    window.history.replaceState(null, '', '/?view=trash')
    fakeApi([email(5, 'Deleted', 'low')])

    render(<App />)

    await screen.findByRole('list', { name: 'Emails' })
    expect(screen.queryByLabelText('Change priority')).not.toBeInTheDocument()
  })

  it('shows the empty message of the current view', async () => {
    window.history.replaceState(null, '', '/?view=unclassified')
    fakeApi([])

    render(<App />)

    expect(await screen.findByText('Nothing to classify.')).toBeInTheDocument()
  })

  it('reloads the list and the counts after a priority change', async () => {
    const urls = fakeApi([email(1, 'One', 'low')])
    render(<App />)
    await screen.findByRole('list', { name: 'Emails' })
    const summaryCalls = () => urls.filter((u) => u === '/api/emails/summary').length
    const before = summaryCalls()

    await userEvent.selectOptions(screen.getByLabelText('Change priority'), 'high')

    await waitFor(() => expect(summaryCalls()).toBe(before + 1))
    expect(urls).toContain('PATCH /api/emails/1')
  })

  it('keeps hidden screen-reader labels inside the scrolling list', async () => {
    // Regression: without `relative`, the rows' sr-only (position: absolute)
    // labels escaped the scroll area and the whole page scrolled into blank space
    fakeApi([email(1, 'One', 'low')])

    render(<App />)

    await screen.findByRole('list', { name: 'Emails' })
    const scroller = screen.getByTestId('list-scroll')
    expect(scroller).toHaveClass('relative', 'overflow-y-auto')
    expect(within(scroller).getByText('Change priority')).toHaveClass('sr-only')
  })
})
