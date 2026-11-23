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

function renderRow(overrides: Partial<Email> = {}, onPriorityChange = vi.fn()) {
  render(
    <EmailRow
      email={{ ...EMAIL, ...overrides }}
      saving={false}
      onPriorityChange={onPriorityChange}
    />,
  )
  return onPriorityChange
}

describe('EmailRow', () => {
  it('shows sender, subject and a one-line snippet of the body', () => {
    renderRow()

    expect(screen.getByText('Priya Raman')).toBeInTheDocument()
    expect(screen.getByText('Production database CPU at 98%')).toBeInTheDocument()
    expect(
      screen.getByText(/the orders database is pinned near 98% CPU\. Priya/),
    ).toBeInTheDocument()
  })

  it('shows the priority badge with the reason as a tooltip', () => {
    renderRow()

    const badge = screen.getByTitle(/Production outage affecting checkout\./)
    expect(badge).toHaveTextContent('Critical')
  })

  it('shows "Not classified" for an email without a priority', () => {
    renderRow({ priority: null, priority_reason: null, classification_source: null })

    expect(screen.getByText('Not classified')).toBeInTheDocument()
  })

  it('shows new emails in bold and handled emails greyed out', () => {
    const { unmount } = render(
      <EmailRow email={EMAIL} saving={false} onPriorityChange={vi.fn()} />,
    )
    expect(screen.getByText(EMAIL.subject)).toHaveClass('font-semibold')
    unmount()

    renderRow({ status: 'handled' })

    const subject = screen.getByText(EMAIL.subject)
    expect(subject).not.toHaveClass('font-semibold')
    expect(subject.closest('[data-status]')).toHaveAttribute('data-status', 'handled')
  })

  it('changes the priority with the compact picker', async () => {
    const onPriorityChange = renderRow()

    await userEvent.selectOptions(screen.getByLabelText('Change priority'), 'high')

    expect(onPriorityChange).toHaveBeenCalledWith(7, 'high')
  })
})
