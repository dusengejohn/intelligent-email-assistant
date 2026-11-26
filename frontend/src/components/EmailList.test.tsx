// @vitest-environment jsdom
// The list: a sticky column header, rows on the header's columns, the Trash bar.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
const EMAILS = [email(1, 'critical', 'ai'), email(2, 'moderate', 'rules'), email(3, null, null)]

function renderList(props: Partial<Parameters<typeof EmailList>[0]> = {}) {
  render(
    <EmailList
      emails={EMAILS}
      loading={false}
      emptyText="No emails yet."
      selectedId={null}
      onSelect={vi.fn()}
      {...props}
    />,
  )
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
      expect(element?.className).toContain(COLUMNS)
    }
  })

  it('has no header when the list is empty', () => {
    renderList({ emails: [] })

    expect(screen.queryByTestId('list-header')).not.toBeInTheDocument()
    expect(screen.getByText('No emails yet.')).toBeInTheDocument()
  })

  it('offers "Empty trash" only in the Trash view', async () => {
    const onEmptyTrash = vi.fn()
    renderList({ onEmptyTrash })

    await userEvent.click(screen.getByRole('button', { name: /Empty trash/ }))
    expect(onEmptyTrash).toHaveBeenCalled()
  })

  it('has no "Empty trash" button in normal views', () => {
    renderList()

    expect(screen.queryByRole('button', { name: /Empty trash/ })).not.toBeInTheDocument()
  })
})
