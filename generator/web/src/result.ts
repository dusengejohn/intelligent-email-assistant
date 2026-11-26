// Small pure helpers for the page (kept out of App.tsx so that file only exports
// a component, which React's fast refresh needs).

export const MIN_COUNT = 1
export const MAX_COUNT = 50

/** "10 new emails generated and delivered to the inbox (1 was invalid and skipped)" */
export function resultText(requested: number, delivered: number): string {
  const noun = delivered === 1 ? 'email' : 'emails'
  let text = `${delivered} new ${noun} generated and delivered to the inbox`
  const skipped = requested - delivered
  if (skipped > 0) text += ` (${skipped} ${skipped === 1 ? 'was' : 'were'} invalid and skipped)`
  return text
}
