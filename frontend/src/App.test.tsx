// @vitest-environment jsdom
// The whole page with a fake fetch: layout pieces and the list in API order.
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Email } from './api'

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

function fakeApi(emails: Email[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string) => {
      const body = path === '/api/health' ? { status: 'ok' } : emails
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('lists the emails in the order the API returns them', async () => {
    // Deliberately not sorted by priority: the browser must not re-sort
    fakeApi([email(3, 'Third', 'low'), email(1, 'First', 'critical'), email(2, 'Second', null)])

    render(<App />)

    const list = await screen.findByRole('list', { name: 'Emails' })
    const subjects = within(list)
      .getAllByRole('listitem')
      .map((item) => within(item).getByTestId('subject').textContent)
    expect(subjects).toEqual(['Third', 'First', 'Second'])
  })

  it('shows the toolbar and the "All" view with its count', async () => {
    fakeApi([email(1, 'One', 'high'), email(2, 'Two', 'low')])

    render(<App />)

    expect(screen.getByRole('button', { name: /Classify/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Generate/ })).toBeInTheDocument()
    const views = screen.getByRole('navigation', { name: 'Views' })
    expect(await within(views).findByText('2')).toBeInTheDocument()
    expect(within(views).getByText('All')).toBeInTheDocument()
  })

  it('shows the empty state when there are no emails', async () => {
    fakeApi([])

    render(<App />)

    expect(await screen.findByText(/No emails yet/)).toBeInTheDocument()
  })
})
