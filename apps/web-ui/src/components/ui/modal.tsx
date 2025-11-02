import * as React from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
  initialFocusRef?: React.RefObject<HTMLElement | null>
}

export function Modal({ open, onOpenChange, children, initialFocusRef }: ModalProps) {
  const [mounted, setMounted] = React.useState(false)
  const modalRoot = React.useRef<HTMLElement | null>(null)
  const contentRef = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    modalRoot.current = document.getElementById('hotpass-modal-root') ?? (() => {
      const element = document.createElement('div')
      element.id = 'hotpass-modal-root'
      document.body.appendChild(element)
      return element
    })()
    setMounted(true)
  }, [])

  React.useEffect(() => {
    if (!open) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onOpenChange(false)
      }
      if (event.key === 'Tab' && contentRef.current) {
        // Basic focus trap
        const focusable = contentRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        } else if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        }
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onOpenChange])

  React.useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const target = initialFocusRef?.current ?? contentRef.current?.querySelector<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    target?.focus()
    return () => previouslyFocused?.focus()
  }, [open, initialFocusRef])

  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!mounted || !modalRoot.current || !open) {
    return null
  }

  return createPortal(
    (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
      >
        <div
          className="absolute inset-0 bg-black/50"
          onClick={() => onOpenChange(false)}
        />
        <div
          ref={contentRef}
          className="relative z-10 w-full max-w-4xl overflow-hidden rounded-2xl border border-border bg-background shadow-2xl"
        >
          {children}
        </div>
      </div>
    ),
    modalRoot.current
  )
}

interface ModalHeaderProps {
  title: string
  description?: string
  onClose?: () => void
  className?: string
}

export function ModalHeader({ title, description, onClose, className }: ModalHeaderProps) {
  return (
    <div className={cn('flex items-start justify-between gap-4 border-b px-6 py-5', className)}>
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {onClose && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close"
          className="h-9 w-9 rounded-full"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}

interface ModalBodyProps {
  children: React.ReactNode
  className?: string
}

export function ModalBody({ children, className }: ModalBodyProps) {
  return (
    <div className={cn('max-h-[70vh] overflow-y-auto px-6 py-5', className)}>
      {children}
    </div>
  )
}

interface ModalFooterProps {
  children: React.ReactNode
  className?: string
}

export function ModalFooter({ children, className }: ModalFooterProps) {
  return (
    <div className={cn('flex items-center justify-between gap-3 border-t bg-muted/40 px-6 py-4', className)}>
      {children}
    </div>
  )
}
