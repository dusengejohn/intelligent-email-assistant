// Text and target view of the alert for new urgent emails (story 3.7, pure).
import type { ViewId } from './views'

export interface UrgentCounts {
  critical: number
  high: number
}

/** "2 new critical, 3 new high" / "1 new critical" / null when nothing is urgent. */
export function alertMessage({ critical, high }: UrgentCounts): string | null {
  const parts = []
  if (critical > 0) parts.push(`${critical} new critical`)
  if (high > 0) parts.push(`${high} new high`)
  return parts.length > 0 ? parts.join(', ') : null
}

/** The view the alert opens: the most urgent group with new emails. */
export function alertView({ critical }: UrgentCounts): ViewId {
  return critical > 0 ? 'critical' : 'high'
}
