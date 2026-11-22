interface Props {
  message: string
  onDismiss: () => void
}

/** Red banner with the backend's error message; the rest of the page keeps working. */
export function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between gap-4 rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800"
    >
      <p>{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss error"
        className="shrink-0 rounded px-1 font-semibold hover:bg-red-100"
      >
        ✕
      </button>
    </div>
  )
}
