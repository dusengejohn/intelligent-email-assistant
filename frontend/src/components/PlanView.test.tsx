// @vitest-environment jsdom
// The Plan view (story 4.5): the day's timeline, the summary sentence, the date
// switch and opening an email. The API module is a fake: no server needed.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getPlanning, type Plan } from '../api'
import { PRIORITIES } from '../priorities'
import { PlanView } from './PlanView'

vi.mock('../api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../api')>()
  return { ...real, getPlanning: vi.fn() }
})

const fetchPlan = vi.mocked(getPlanning)

/** Thursday 2026-11-26 in Toronto (UTC-5): the scenario from story 4.4. */
function thursday(overrides: Partial<Plan> = {}): Plan {
  return {
    date: '2026-11-26',
    timezone: 'America/Toronto',
    window: { start: '2026-11-26T14:00:00Z', end: '2026-11-26T22:00:00Z' },
    events: [
      { id: '2026-11-26-1', title: 'Stand-up', start: '2026-11-26T14:30:00Z', end: '2026-11-26T14:45:00Z' },
      { id: '2026-11-26-2', title: 'Lunch', start: '2026-11-26T17:00:00Z', end: '2026-11-26T18:00:00Z' },
    ],
    free_slots: [],
    suggestions: [
      {
        start: '2026-11-26T14:00:00Z',
        end: '2026-11-26T14:20:00Z',
        priority: 'critical',
        emails: [{ id: 2, subject: 'Breach suspected', priority: 'critical', minutes: 20 }],
      },
      {
        start: '2026-11-26T21:50:00Z',
        end: '2026-11-26T22:00:00Z',
        priority: 'low',
        emails: [
          { id: 6, subject: 'Newsletter', priority: 'low', minutes: 5 },
          { id: 7, subject: 'FYI', priority: 'low', minutes: 5 },
        ],
      },
    ],
    not_today: [{ id: 5, subject: 'Long design doc', priority: 'moderate', minutes: 90 }],
    unclassified: 2,
    ...overrides,
  }
}

function timelineItems() {
  return within(screen.getByRole('list', { name: 'Timeline' })).getAllByRole('listitem', {
    name: /./,
  })
}

beforeEach(() => {
  fetchPlan.mockResolvedValue(thursday())
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('PlanView', () => {
  it('asks for today first (no date)', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    await screen.findByRole('list', { name: 'Timeline' })
    expect(fetchPlan).toHaveBeenCalledWith(undefined)
    expect(screen.getByRole('heading', { name: 'Plan for Thursday, November 26' })).toBeInTheDocument()
  })

  it('shows meetings and reply blocks in time order, in Toronto time', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    await screen.findByRole('list', { name: 'Timeline' })
    expect(timelineItems().map((item) => item.getAttribute('aria-label'))).toEqual([
      '09:00–09:20 Critical: 1 email',
      '09:30–09:45 Meeting: Stand-up',
      '12:00–13:00 Meeting: Lunch',
      '16:50–17:00 Low: 2 emails',
    ])
  })

  it('colors reply blocks by priority and keeps meetings grey', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    const [critical, standUp] = await waitFor(() => timelineItems())
    expect(critical).toHaveStyle({ borderLeftColor: PRIORITIES.critical.color })
    expect(critical).toHaveAttribute('data-kind', 'reply')
    expect(standUp).toHaveAttribute('data-kind', 'meeting')
  })

  it('places items by time: 09:00-09:20 is the top 4.17 % of the day', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    const [critical] = await waitFor(() => timelineItems())
    expect(critical.style.top).toBe('0%')
    expect(critical.style.height).toMatch(/^4\.16/)
  })

  it('shows the summary sentence', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    expect(
      await screen.findByText(
        '1 critical email planned from 09:00 to 09:20; 2 low emails batched at 16:50; ' +
          '1 doesn’t fit today; 2 unclassified (Classify first).',
      ),
    ).toBeInTheDocument()
  })

  it('opens an email from a reply block or from the waiting list', async () => {
    const onOpen = vi.fn()
    render(<PlanView reloadKey={0} selectedId={null} onOpen={onOpen} />)

    await userEvent.click(await screen.findByRole('button', { name: /Breach suspected/ }))
    await userEvent.click(screen.getByRole('button', { name: /FYI/ }))
    const waiting = screen.getByRole('region', { name: 'Doesn’t fit today' })
    await userEvent.click(within(waiting).getByRole('button', { name: /Long design doc/ }))

    expect(onOpen.mock.calls).toEqual([[2], [7], [5]])
  })

  it('marks the open email', async () => {
    render(<PlanView reloadKey={0} selectedId={7} onOpen={vi.fn()} />)

    expect(await screen.findByRole('button', { name: /FYI/ })).toHaveAttribute('aria-current', 'true')
  })

  it('steps to the next day and back to today; the past is disabled', async () => {
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)
    await screen.findByRole('list', { name: 'Timeline' })
    expect(screen.getByRole('button', { name: 'Previous day' })).toBeDisabled()

    fetchPlan.mockResolvedValue(thursday({ date: '2026-11-27' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next day' }))

    expect(fetchPlan).toHaveBeenLastCalledWith('2026-11-27')
    await screen.findByRole('heading', { name: 'Plan for Friday, November 27' })
    expect(screen.getByRole('button', { name: 'Previous day' })).toBeEnabled()

    fetchPlan.mockResolvedValue(thursday())
    await userEvent.click(screen.getByRole('button', { name: 'Today' }))
    expect(fetchPlan).toHaveBeenLastCalledWith(undefined)
  })

  it('loads again when the app reloads (new mail, Classify, handled)', async () => {
    const { rerender } = render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)
    await screen.findByRole('list', { name: 'Timeline' })

    rerender(<PlanView reloadKey={1} selectedId={null} onOpen={vi.fn()} />)

    await waitFor(() => expect(fetchPlan).toHaveBeenCalledTimes(2))
  })

  it('says when the working day is over', async () => {
    fetchPlan.mockResolvedValue(thursday({ window: null, suggestions: [], free_slots: [] }))
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    expect(await screen.findByText(/The working day is over/)).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Timeline' })).not.toBeInTheDocument()
  })

  it('shows an error and keeps working', async () => {
    fetchPlan.mockRejectedValueOnce(new ApiError('Cannot reach the server. Is the backend running?', 0))
    render(<PlanView reloadKey={0} selectedId={null} onOpen={vi.fn()} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server')
  })
})
