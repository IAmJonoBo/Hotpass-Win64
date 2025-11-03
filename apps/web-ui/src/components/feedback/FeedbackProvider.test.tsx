import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { FeedbackProvider, useFeedback } from './FeedbackProvider'

const TestConsumer = () => {
  const { addFeedback } = useFeedback()
  return (
    <button
      type="button"
      onClick={() => addFeedback({ title: 'Hello', description: 'World', autoClose: false })}
    >
      Trigger
    </button>
  )
}

describe('FeedbackProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('exposes addFeedback and renders messages', () => {
    render(
      <FeedbackProvider>
        <TestConsumer />
      </FeedbackProvider>,
    )

    fireEvent.click(screen.getByText('Trigger'))

    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('World')).toBeInTheDocument()
  })

  it('dismisses messages when the dismiss action is clicked', () => {
    render(
      <FeedbackProvider>
        <TestConsumer />
      </FeedbackProvider>,
    )

    fireEvent.click(screen.getByText('Trigger'))
    fireEvent.click(screen.getByText('Dismiss'))

    expect(screen.queryByText('Hello')).not.toBeInTheDocument()
  })

  it('automatically dismisses messages when autoClose is true', () => {
    const AutoCloseConsumer = () => {
      const { addFeedback } = useFeedback()
      return (
        <button
          type="button"
          onClick={() => addFeedback({ title: 'Auto', autoClose: true, timeoutMs: 1000 })}
        >
          AutoTrigger
        </button>
      )
    }

    render(
      <FeedbackProvider>
        <AutoCloseConsumer />
      </FeedbackProvider>,
    )

    fireEvent.click(screen.getByText('AutoTrigger'))
    expect(screen.getByText('Auto')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(1000)
    })

    expect(screen.queryByText('Auto')).not.toBeInTheDocument()
  })

  it('throws when useFeedback is used outside the provider', () => {
    const BrokenConsumer = () => {
      useFeedback()
      return null
    }

    expect(() => render(<BrokenConsumer />)).toThrow('useFeedback must be used within a FeedbackProvider')
  })
})
