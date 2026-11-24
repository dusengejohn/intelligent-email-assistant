// @vitest-environment jsdom
// The Notification API wrapper, with a fake Notification class (no real browser).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { notificationsSupported, notify, permission, requestPermission } from './notifications'

/** A fake browser Notification: records what was shown. */
function fakeNotification(state: NotificationPermission, answer: NotificationPermission = state) {
  const shown: { title: string; body?: string; instance: { onclick: (() => void) | null } }[] = []
  class FakeNotification {
    static permission = state
    static requestPermission = vi.fn(async () => answer)
    onclick: (() => void) | null = null
    constructor(title: string, options?: NotificationOptions) {
      shown.push({ title, body: options?.body, instance: this })
    }
  }
  vi.stubGlobal('Notification', FakeNotification)
  return { shown, FakeNotification }
}

function pageVisible(visible: boolean) {
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue(visible ? 'visible' : 'hidden')
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('notifications', () => {
  it('reports "unsupported" when the browser has no Notification API', () => {
    vi.stubGlobal('Notification', undefined)

    expect(notificationsSupported()).toBe(false)
    expect(permission()).toBe('unsupported')
  })

  it('passes on the browser permission and the answer to a request', async () => {
    const { FakeNotification } = fakeNotification('default', 'granted')

    expect(permission()).toBe('default')
    expect(await requestPermission()).toBe('granted')
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1)
  })

  it('shows a notification when allowed and the page is in the background', () => {
    const { shown } = fakeNotification('granted')
    pageVisible(false)
    const onClick = vi.fn()

    notify('New urgent emails', '1 new critical', onClick)

    expect(shown).toHaveLength(1)
    expect(shown[0]).toMatchObject({ title: 'New urgent emails', body: '1 new critical' })
    shown[0].instance.onclick?.()
    expect(onClick).toHaveBeenCalled()
  })

  it('stays quiet while the page is visible (the toast is enough)', () => {
    const { shown } = fakeNotification('granted')
    pageVisible(true)

    notify('New urgent emails', '1 new critical', vi.fn())

    expect(shown).toHaveLength(0)
  })

  it.each(['denied', 'default'] as const)('does nothing (and no error) when permission is %s', (state) => {
    const { shown } = fakeNotification(state)
    pageVisible(false)

    expect(() => notify('t', 'b', vi.fn())).not.toThrow()
    expect(shown).toHaveLength(0)
  })

  it('does nothing when the browser has no Notification API', () => {
    vi.stubGlobal('Notification', undefined)
    pageVisible(false)

    expect(() => notify('t', 'b', vi.fn())).not.toThrow()
  })
})
