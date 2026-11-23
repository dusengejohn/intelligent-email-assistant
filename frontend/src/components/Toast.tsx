import { useEffect } from 'react'

interface Props {
  message: string
  actionLabel?: string // e.g. "Undo"
  onAction?: () => void
  onDismiss: () => void
  timeoutMs?: number
}

/**
 * A small, temporary message at the bottom of the screen that doesn't block the
 * page. role="status" makes screen readers announce it politely. It hides itself
 * after `timeoutMs`, and can carry one action (Undo). Reused by story 3.7 alerts.
 */
export function Toast({ message, actionLabel, onAction, onDismiss, timeoutMs = 8000 }: Props) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, timeoutMs)
    return () => window.clearTimeout(timer) // a new toast restarts the countdown
  }, [message, onDismiss, timeoutMs])

  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-30 flex -translate-x-1/2 items-center gap-4 rounded-lg bg-gray-900 px-4 py-2 text-sm text-white shadow-lg"
    >
      <span>{message}</span>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="font-semibold text-blue-300 underline-offset-2 hover:underline"
        >
          {actionLabel}
        </button>
      )}
      <button type="button" onClick={onDismiss} aria-label="Close" className="text-gray-400 hover:text-white">
        ✕
      </button>
    </div>
  )
}
