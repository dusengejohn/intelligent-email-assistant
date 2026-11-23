// @vitest-environment jsdom
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { EmailSummary } from '../api'
import { Sidebar, ViewSelect } from './Sidebar'

const SUMMARY: EmailSummary = {
  all: 125,
  unclassified: 10,
  classified: 115,
  critical: 31,
  high: 23,
  moderate: 40,
  low: 21,
  handled: 1,
  trash: 2,
}

describe('Sidebar', () => {
  it('shows every view with its count', () => {
    render(<Sidebar active="all" summary={SUMMARY} onSelect={vi.fn()} />)

    const nav = screen.getByRole('navigation', { name: 'Views' })
    const buttons = within(nav).getAllByRole('button')
    expect(buttons).toHaveLength(8)
    expect(within(nav).getByRole('button', { name: /Unclassified/ })).toHaveTextContent('10')
    expect(within(nav).getByRole('button', { name: /Critical/ })).toHaveTextContent('31')
    expect(within(nav).getByRole('button', { name: /Trash/ })).toHaveTextContent('2')
  })

  it('marks the active view for screen readers', () => {
    render(<Sidebar active="high" summary={SUMMARY} onSelect={vi.fn()} />)

    expect(screen.getByRole('button', { name: /High/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /All/ })).not.toHaveAttribute('aria-current')
  })

  it('selects a view by click and by keyboard', async () => {
    const onSelect = vi.fn()
    render(<Sidebar active="all" summary={SUMMARY} onSelect={onSelect} />)

    await userEvent.click(screen.getByRole('button', { name: /Moderate/ }))
    expect(onSelect).toHaveBeenLastCalledWith('moderate')

    screen.getByRole('button', { name: /Low/ }).focus()
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenLastCalledWith('low')
  })

  it('shows no numbers while the counts are loading', () => {
    render(<Sidebar active="all" summary={null} onSelect={vi.fn()} />)

    expect(screen.getByRole('button', { name: /All/ })).toHaveTextContent(/^All$/)
  })
})

describe('ViewSelect (narrow screens)', () => {
  it('selects a view from the dropdown', async () => {
    const onSelect = vi.fn()
    render(<ViewSelect active="all" summary={SUMMARY} onSelect={onSelect} />)

    await userEvent.selectOptions(screen.getByLabelText('View'), 'trash')

    expect(onSelect).toHaveBeenCalledWith('trash')
  })
})
