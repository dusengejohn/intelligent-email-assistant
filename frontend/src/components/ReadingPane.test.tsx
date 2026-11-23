// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Email } from '../api'
import { ReadingPane } from './ReadingPane'

const EMAIL: Email = {
  id: 7,
  sender_name: 'Priya Raman',
  sender_email: 'priya.raman@example.com',
  subject: 'Production database CPU at 98%',
  body: 'Team,\n\nThe orders database is pinned near 98% CPU.\n\nPriya',
  received_at: '2026-11-21T15:00:00Z',
  priority: 'critical',
  priority_reason: 'Production outage affecting checkout.',
  classification_source: 'ai',
  suggested_response_minutes: 15,
  status: 'new',
  created_at: '2026-11-21T15:01:00Z',
  deleted_at: null,
}

function handlers() {
  return {
    onPriorityChange: vi.fn(),
    onToggleHandled: vi.fn(),
    onReclassify: vi.fn(),
    onDelete: vi.fn(),
    onRestore: vi.fn(),
    onClose: vi.fn(),
  }
}

describe('ReadingPane', () => {
  it('shows the whole email with its line breaks and the classification', () => {
    render(<ReadingPane email={EMAIL} inTrash={false} busy={false} {...handlers()} />)

    expect(screen.getByRole('heading', { name: EMAIL.subject })).toBeInTheDocument()
    expect(screen.getByText(/priya\.raman@example\.com/)).toBeInTheDocument()
    const body = screen.getByTestId('email-body')
    expect(body.textContent).toBe(EMAIL.body) // line breaks kept
    expect(body).toHaveClass('whitespace-pre-wrap')
    expect(screen.getByText('Production outage affecting checkout.')).toBeInTheDocument()
    expect(screen.getByText(/15 min/)).toBeInTheDocument()
  })

  it('offers the actions for an email in the inbox', async () => {
    const h = handlers()
    render(<ReadingPane email={EMAIL} inTrash={false} busy={false} {...h} />)

    await userEvent.selectOptions(screen.getByLabelText('Change priority'), 'high')
    await userEvent.click(screen.getByRole('button', { name: 'Mark handled' }))
    await userEvent.click(screen.getByRole('button', { name: /Re-classify/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await userEvent.click(screen.getByRole('button', { name: /Back to list/ }))

    expect(h.onPriorityChange).toHaveBeenCalledWith('high')
    expect(h.onToggleHandled).toHaveBeenCalled()
    expect(h.onReclassify).toHaveBeenCalled()
    expect(h.onDelete).toHaveBeenCalled()
    expect(h.onClose).toHaveBeenCalled()
  })

  it('says "Mark as new" for a handled email', () => {
    render(<ReadingPane email={{ ...EMAIL, status: 'handled' }} inTrash={false} busy={false} {...handlers()} />)

    expect(screen.getByRole('button', { name: 'Mark as new' })).toBeInTheDocument()
  })

  it('only offers Restore for an email in the Trash', async () => {
    const h = handlers()
    render(<ReadingPane email={{ ...EMAIL, deleted_at: '2026-11-23T10:00:00Z' }} inTrash busy={false} {...h} />)

    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))

    expect(h.onRestore).toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Change priority')).not.toBeInTheDocument()
  })

  it('disables the actions while one is running', () => {
    render(<ReadingPane email={EMAIL} inTrash={false} busy {...handlers()} />)

    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled()
  })
})
