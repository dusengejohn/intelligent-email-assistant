import type { Email, Priority } from '../api'
import { EmailCard } from './EmailCard'

interface Props {
  emails: Email[]
  loading: boolean
  savingId: number | null
  onPriorityChange: (id: number, priority: Priority) => void
}

export function EmailList({ emails, loading, savingId, onPriorityChange }: Props) {
  if (loading) {
    return <p className="text-sm text-gray-500">Loading emails…</p>
  }
  if (emails.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500">
        No emails yet. Click Generate to create some.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-3">
      {emails.map((email) => (
        // key: lets React track each card between renders
        <li key={email.id}>
          <EmailCard
            email={email}
            saving={savingId === email.id}
            onPriorityChange={onPriorityChange}
          />
        </li>
      ))}
    </ul>
  )
}
