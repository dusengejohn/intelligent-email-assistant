// @vitest-environment jsdom
// Component tests: render the row in a simulated browser and check what a user sees.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Email } from '../api'
import { EmailRow } from './EmailRow'

const EMAIL: Email = {
  id: 7,
  sender_name: 'Priya Raman',
  sender_email: 'priya.raman@example.com',
  subject: 'Production database CPU at 98%',
  body: 'Team,\nthe orders database is pinned near 98% CPU.\nPriya',
  received_at: '2026-11-21T15:00:00Z',
  priority: 'critical',
  priority_reason: 'Production outage affecting checkout.',
  classification_source: 'ai',
  suggested_response_minutes: 15,
  status: 'new',
  created_at: '2026-11-21T15:01:00Z',
  deleted_at: null,
}

function renderRow(overrides: Partial<Email> = {}, selected = false, onSelect = vi.fn()) {
  render(<EmailRow email={{ ...EMAIL, ...overrides }} selected={selected} onSelect={onSelect} />)
  return onSelect
}

describe('EmailRow', () => {
  it('shows badge, sender, subject and a one-line snippet', () => {
    renderRow()

    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Priya Raman')).toBeInTheDocument()
    expect(screen.getByText('Production database CPU at 98%')).toBeInTheDocument()
    expect(
      screen.getByText(/the orders database is pinned near 98% CPU\. Priya/),
    ).toBeInTheDocument()
  })

  it('shows "Not classified" for an email without a priority', () => {
    renderRow({ priority: null, priority_reason: null, classification_source: null })

    expect(screen.getByText('Not classified')).toBeInTheDocument()
  })

  it('shows new emails in bold and handled emails greyed out', () => {
    const { unmount } = render(<EmailRow email={EMAIL} selected={false} onSelect={vi.fn()} />)
    expect(screen.getByText(EMAIL.subject)).toHaveClass('font-semibold')
    unmount()

    renderRow({ status: 'handled' })

    const subject = screen.getByText(EMAIL.subject)
    expect(subject).not.toHaveClass('font-semibold')
    expect(subject.closest('[data-status]')).toHaveAttribute('data-status', 'handled')
  })

  it('is a button that opens the email (mouse and keyboard)', async () => {
    const onSelect = renderRow()
    const row = screen.getByRole('button', { name: /Production database CPU at 98%/ })

    await userEvent.click(row)
    row.focus()
    await userEvent.keyboard('{Enter}')

    expect(onSelect).toHaveBeenCalledTimes(2)
    expect(onSelect).toHaveBeenCalledWith(7)
  })

  it('marks the selected row for screen readers', () => {
    renderRow({}, true)

    expect(screen.getByRole('button', { name: /Production database/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('has no priority dropdown anymore (it moved to the reading pane)', () => {
    renderRow()

    expect(screen.queryByLabelText('Change priority')).not.toBeInTheDocument()
  })
})
