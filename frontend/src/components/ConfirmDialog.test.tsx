// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

function renderDialog() {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <ConfirmDialog
      title="Empty the Trash?"
      message="Permanently delete 2 emails? This can't be undone."
      confirmLabel="Delete forever"
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  )
  return { onConfirm, onCancel }
}

describe('ConfirmDialog', () => {
  it('is announced as a modal dialog with its message', () => {
    renderDialog()

    const dialog = screen.getByRole('dialog', { name: 'Empty the Trash?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveTextContent("This can't be undone.")
  })

  it('puts the focus on the safe choice', () => {
    renderDialog()

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
  })

  it('cancels with Esc and with the Cancel button', async () => {
    const { onCancel, onConfirm } = renderDialog()

    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onCancel).toHaveBeenCalledTimes(2)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('confirms with the confirm button', async () => {
    const { onConfirm } = renderDialog()

    await userEvent.click(screen.getByRole('button', { name: 'Delete forever' }))

    expect(onConfirm).toHaveBeenCalled()
  })
})
