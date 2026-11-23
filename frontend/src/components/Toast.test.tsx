// @vitest-environment jsdom
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Toast } from './Toast'

afterEach(() => {
  vi.useRealTimers()
})

describe('Toast', () => {
  it('shows the message politely and runs its action', async () => {
    const onAction = vi.fn()
    render(<Toast message="Email moved to Trash." actionLabel="Undo" onAction={onAction} onDismiss={vi.fn()} />)

    expect(screen.getByRole('status')).toHaveTextContent('Email moved to Trash.')
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))

    expect(onAction).toHaveBeenCalled()
  })

  it('hides itself after the timeout', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()
    render(<Toast message="Done." onDismiss={onDismiss} timeoutMs={8000} />)

    act(() => vi.advanceTimersByTime(7999))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalled()
  })
})
