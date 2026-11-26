// @vitest-environment jsdom
// Component tests for the generator page: React Testing Library in a simulated
// browser; the API module is replaced by a fake, so no server is needed.
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ApiError, generateEmails, type GenerateResult } from './api'
import { resultText } from './result'

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>()
  return { ...real, generateEmails: vi.fn() }
})

const generate = vi.mocked(generateEmails)

afterEach(() => {
  vi.clearAllMocks()
})

/** A promise the test resolves or rejects when it wants (to see the running state). */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function countField() {
  return screen.getByRole('spinbutton', { name: /how many emails/i })
}

function scenarioField() {
  return screen.getByRole('textbox', { name: /scenario/i })
}

function generateButton() {
  // "Generate", or "Generating…" while it runs
  return screen.getByRole('button', { name: /^generat/i })
}

describe('generator page', () => {
  it('shows the form with 10 emails by default', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: /email generator/i })).toBeInTheDocument()
    expect(countField()).toHaveValue(10)
    expect(scenarioField()).toHaveValue('')
    expect(generateButton()).toBeEnabled()
  })

  it('generates, then says how many were delivered and links to the inbox', async () => {
    generate.mockResolvedValue({ generated: 10, delivered: 10 })
    const user = userEvent.setup()
    render(<App />)

    await user.type(scenarioField(), 'Hospital IT team')
    await user.click(generateButton())

    expect(generate).toHaveBeenCalledWith(10, 'Hospital IT team')
    expect(
      await screen.findByText('10 new emails generated and delivered to the inbox'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the inbox/i })).toHaveAttribute(
      'href',
      'http://localhost:8080',
    )
  })

  it('says one email in the singular', async () => {
    generate.mockResolvedValue({ generated: 1, delivered: 1 })
    const user = userEvent.setup()
    render(<App />)

    await user.clear(countField())
    await user.type(countField(), '1')
    await user.click(generateButton())

    expect(
      await screen.findByText('1 new email generated and delivered to the inbox'),
    ).toBeInTheDocument()
  })

  it('mentions emails Claude produced invalid (fewer than requested)', async () => {
    generate.mockResolvedValue({ generated: 9, delivered: 9 })
    const user = userEvent.setup()
    render(<App />)

    await user.click(generateButton())

    expect(
      await screen.findByText(
        '9 new emails generated and delivered to the inbox (1 was invalid and skipped)',
      ),
    ).toBeInTheDocument()
  })

  it('disables the form and says "Generating…" while it runs', async () => {
    const pending = deferred<GenerateResult>()
    generate.mockReturnValue(pending.promise)
    const user = userEvent.setup()
    render(<App />)

    await user.click(generateButton())

    expect(generateButton()).toBeDisabled()
    expect(generateButton()).toHaveTextContent('Generating…')
    expect(countField()).toBeDisabled()
    expect(scenarioField()).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/about 15 s per 10 emails/i)

    pending.resolve({ generated: 10, delivered: 10 })
    expect(await screen.findByText(/10 new emails/)).toBeInTheDocument()
    expect(generateButton()).toBeEnabled()
  })

  it('shows an API error in an alert and clears it on the next try', async () => {
    generate.mockRejectedValueOnce(
      new ApiError('Generated 10 emails but the inbox could not be reached. Nothing was delivered.', 502),
    )
    generate.mockResolvedValueOnce({ generated: 10, delivered: 10 })
    const user = userEvent.setup()
    render(<App />)

    await user.click(generateButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(/inbox could not be reached/)
    expect(screen.queryByRole('link', { name: /open the inbox/i })).not.toBeInTheDocument()
    expect(generateButton()).toBeEnabled()

    await user.click(generateButton())

    expect(await screen.findByText(/10 new emails/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it.each(['0', '51', '2.5', ''])('cannot generate with count %j', async (value) => {
    const user = userEvent.setup()
    render(<App />)

    await user.clear(countField())
    if (value) await user.type(countField(), value)

    expect(generateButton()).toBeDisabled()
    await user.type(scenarioField(), '{Enter}')
    expect(generate).not.toHaveBeenCalled()
  })

  it('checks the count itself too, not only through the browser', async () => {
    // fireEvent.submit skips the browser's own form validation (min/max/required)
    const user = userEvent.setup()
    render(<App />)

    await user.clear(countField())
    await user.type(countField(), '0')
    fireEvent.submit(countField().closest('form')!)

    expect(generate).not.toHaveBeenCalled()
  })

  it('submits with Enter in the scenario field', async () => {
    generate.mockResolvedValue({ generated: 10, delivered: 10 })
    const user = userEvent.setup()
    render(<App />)

    await user.type(scenarioField(), 'Retail{Enter}')

    expect(generate).toHaveBeenCalledWith(10, 'Retail')
  })
})

describe('resultText', () => {
  it.each([
    [10, 10, '10 new emails generated and delivered to the inbox'],
    [1, 1, '1 new email generated and delivered to the inbox'],
    [10, 9, '9 new emails generated and delivered to the inbox (1 was invalid and skipped)'],
    [10, 7, '7 new emails generated and delivered to the inbox (3 were invalid and skipped)'],
  ])('requested %i, delivered %i', (requested, delivered, text) => {
    expect(resultText(requested, delivered)).toBe(text)
  })
})
