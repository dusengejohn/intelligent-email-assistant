// Priority labels and colors (brief §7), mirroring backend/app/priorities.py.
// Keep the one-line entry format below: a backend test
// (tests/test_frontend_priorities_sync.py) reads this file and fails if the
// labels or colors drift from the Python source of truth.
import type { ClassificationSource, Priority } from './api'

export const PRIORITIES: Record<Priority, { label: string; color: string }> = {
  critical: { label: 'Critical', color: '#DC2626' },
  high: { label: 'High', color: '#EA580C' },
  moderate: { label: 'Moderate', color: '#CA8A04' },
  low: { label: 'Low', color: '#16A34A' },
}

/** Sort order everywhere (brief §7): most urgent first. */
export const PRIORITY_ORDER: Priority[] = ['critical', 'high', 'moderate', 'low']

/** How each source is shown on the card. */
export const SOURCE_LABEL: Record<ClassificationSource, string> = {
  ai: 'AI',
  rules: 'rules',
  manual: 'manual',
}
