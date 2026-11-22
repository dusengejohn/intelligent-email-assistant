import type { Email } from '../api'

/** UTC ISO string from the API -> date and time in the browser's own timezone. */
function localDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function EmailCard({ email }: { email: Email }) {
  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm">
          <span className="font-semibold text-gray-900">{email.sender_name}</span>{' '}
          <span className="text-gray-500">&lt;{email.sender_email}&gt;</span>
        </p>
        <time dateTime={email.received_at} className="text-xs text-gray-500">
          {localDateTime(email.received_at)}
        </time>
      </header>
      <h3 className="mt-1 font-medium text-gray-900">{email.subject}</h3>
      {/* line-clamp-2: show at most two lines, with "…" */}
      <p className="mt-1 line-clamp-2 text-sm text-gray-600">{email.body}</p>
    </article>
  )
}
