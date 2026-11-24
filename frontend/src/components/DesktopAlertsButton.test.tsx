// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DesktopAlertsButton } from './DesktopAlertsButton'

function fakeNotification(state: NotificationPermission, answer: NotificationPermission = state) {
  const requestPermission = vi.fn(async () => {
    FakeNotification.permission = answer
    return answer
  })
  class FakeNotification {
    static permission: NotificationPermission = state
    static requestPermission = requestPermission
  }
  vi.stubGlobal('Notification', FakeNotification)
  return requestPermission
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DesktopAlertsButton', () => {
  it('asks for permission only when clicked', async () => {
    const requestPermission = fakeNotification('default', 'granted')
    render(<DesktopAlertsButton />)
    expect(requestPermission).not.toHaveBeenCalled() // never on its own

    await userEvent.click(screen.getByRole('button', { name: 'Enable desktop alerts' }))

    expect(requestPermission).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Desktop alerts on')).toBeInTheDocument()
  })

  it('says when alerts are already on', () => {
    fakeNotification('granted')
    render(<DesktopAlertsButton />)

    expect(screen.getByText('Desktop alerts on')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('explains when the browser blocks alerts (no error)', () => {
    fakeNotification('denied')
    render(<DesktopAlertsButton />)

    expect(screen.getByText(/blocked/)).toBeInTheDocument()
  })

  it('shows nothing when the browser has no notifications', () => {
    vi.stubGlobal('Notification', undefined)
    const { container } = render(<DesktopAlertsButton />)

    expect(container).toBeEmptyDOMElement()
  })
})
