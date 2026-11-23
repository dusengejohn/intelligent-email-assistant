// Which email to open after the open one leaves the view (deleted, restored...):
// the one below it, else the one above, else nothing. Like a mail client.

export function nextSelection(ids: number[], removedId: number): number | null {
  const index = ids.indexOf(removedId)
  if (index === -1) return ids[0] ?? null
  return ids[index + 1] ?? ids[index - 1] ?? null
}
