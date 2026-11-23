// @vitest-environment jsdom
// The list: a sticky column header, and rows that share the header's columns.
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Email } from '../api'
import { COLUMNS } from './columns'
import { EmailList } from './EmailList'

function email(id: number, priority: Email['priority'], source: Email['classification_source']): Email {
  return {
    id,
    sender_name: `Sender ${id}`,
    sender_email: `s${id}@example.com`,
    subject: `Subject ${id}`,
    body: 'Body',
    received_at: '2026-11-21T15:00:00Z',
    priority,
    priority_reason: priority ? 'Reason.' : null,
    classification_source: source,
    suggested_response_minutes: priority ? 15 : null,
    status: 'new',
    created_at: '2026-11-21T15:00:00Z',
    deleted_at: null,
  }
}

// Badges of very different widths: with content-sized parts, the columns drifted apart
const EMAILS = [
  email(1, 'critical', 'ai'),
  email(2, 'moderate', 'fallback'),
  email(3, null, null),
]

function renderList() {
  render(<EmailList emails={EMAILS} loading={false} savingId={null} onPriorityChange={vi.fn()} />)
}

describe('EmailList', () => {
  it('has a column header that stays at the top while the list scrolls', () => {
    renderList()

    const header = screen.getByTestId('list-header')
    for (const name of ['Priority', 'From', 'Subject', 'Received']) {
      expect(within(header).getByText(name)).toBeInTheDocument()
    }
    expect(header).toHaveClass('sticky', 'top-0')
  })

  it('lays out the header and every row on the same columns', () => {
    renderList()

    const header = screen.getByTestId('list-header')
    const rows = screen.getAllByRole('listitem').map((item) => item.firstElementChild)
    expect(rows).toHaveLength(3)
    for (const element of [header, ...rows]) {
      // Same column template => sender, subject and date line up on every row,
      // whatever the width of the badge
      expect(element?.className).toContain(COLUMNS)
    }
  })

  it('has no header when the list is empty', () => {
    render(<EmailList emails={[]} loading={false} savingId={null} onPriorityChange={vi.fn()} />)

    expect(screen.queryByTestId('list-header')).not.toBeInTheDocument()
  })
})
