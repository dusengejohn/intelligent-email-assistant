import { useState } from 'react'
import { permission, requestPermission, type AlertPermission } from '../notifications'

/**
 * Opt-in for desktop notifications. Permission is ONLY requested when this is
 * clicked, never on page load. Denied or unsupported: alerts stay in-page.
 */
export function DesktopAlertsButton() {
  const [state, setState] = useState<AlertPermission>(() => permission())

  if (state === 'unsupported') return null
  if (state === 'granted') {
    return <span className="text-xs text-gray-500">Desktop alerts on</span>
  }
  if (state === 'denied') {
    return (
      <span className="text-xs text-gray-500" title="Allow notifications for this site in the browser settings">
        Desktop alerts blocked in the browser
      </span>
    )
  }
  return (
    <button
      type="button"
      onClick={async () => setState(await requestPermission())}
      className="text-xs text-blue-700 underline-offset-2 hover:underline"
    >
      Enable desktop alerts
    </button>
  )
}
