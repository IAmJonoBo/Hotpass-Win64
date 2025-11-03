import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiBanner } from './ApiBanner'

type FeedbackVariant = 'error' | 'warning' | 'info' | 'success'

export interface FeedbackMessage {
  id: string
  title: string
  description?: string
  variant?: FeedbackVariant
  badge?: string
  autoClose?: boolean
  timeoutMs?: number
}

interface FeedbackContextValue {
  addFeedback: (message: Omit<FeedbackMessage, 'id'> & { id?: string }) => string
  dismissFeedback: (id: string) => void
}

const FeedbackContext = createContext<FeedbackContextValue | undefined>(undefined)

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<FeedbackMessage[]>([])

  const dismissFeedback = useCallback((id: string) => {
    setMessages(prev => prev.filter(message => message.id !== id))
  }, [])

  const addFeedback = useCallback(
    (message: Omit<FeedbackMessage, 'id'> & { id?: string }) => {
      const id = message.id ?? `feedback-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
      const payload: FeedbackMessage = {
        autoClose: true,
        timeoutMs: 8000,
        variant: 'info',
        ...message,
        id,
      }
      setMessages(prev => [payload, ...prev])

      if (payload.autoClose) {
        window.setTimeout(() => dismissFeedback(id), payload.timeoutMs)
      }

      return id
    },
    [dismissFeedback],
  )

  const value = useMemo<FeedbackContextValue>(
    () => ({
      addFeedback,
      dismissFeedback,
    }),
    [addFeedback, dismissFeedback],
  )

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed top-24 right-6 z-50 flex w-[340px] max-w-[calc(100%-1.5rem)] flex-col gap-3">
        {messages.map(message => (
          <ApiBanner
            key={message.id}
            title={message.title}
            description={message.description}
            variant={message.variant}
            badge={message.badge}
            className="pointer-events-auto shadow-lg"
            action={
              <button
                type="button"
                onClick={() => dismissFeedback(message.id)}
                className="text-xs font-medium text-muted-foreground underline"
              >
                Dismiss
              </button>
            }
          />
        ))}
      </div>
    </FeedbackContext.Provider>
  )
}

export function useFeedback(): FeedbackContextValue {
  const context = useContext(FeedbackContext)
  if (!context) {
    throw new Error('useFeedback must be used within a FeedbackProvider')
  }
  return context
}
