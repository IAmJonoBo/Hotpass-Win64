/**
 * Sheet/Drawer component using shadcn/ui patterns
 */

import * as React from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

interface SheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
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

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50"
        onClick={() => onOpenChange(false)}
      />
      {/* Sheet */}
      <div className="fixed inset-y-0 right-0 z-50 w-full sm:max-w-lg bg-background shadow-lg">
        {children}
      </div>
    </>
  )
}

interface SheetContentProps {
  children: React.ReactNode
  className?: string
}

export function SheetContent({ children, className }: SheetContentProps) {
  return (
    <div className={cn('flex h-full flex-col', className)}>
      {children}
    </div>
  )
}

interface SheetHeaderProps {
  children: React.ReactNode
  onClose?: () => void
}

export function SheetHeader({ children, onClose }: SheetHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b p-6">
      <div className="flex-1">{children}</div>
      {onClose && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close panel"
          className="h-8 w-8"
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </div>
  )
}

interface SheetTitleProps {
  children: React.ReactNode
}

export function SheetTitle({ children }: SheetTitleProps) {
  return <h2 className="text-lg font-semibold">{children}</h2>
}

interface SheetBodyProps {
  children: React.ReactNode
  className?: string
}

export function SheetBody({ children, className }: SheetBodyProps) {
  return (
    <div className={cn('flex-1 overflow-y-auto p-6', className)}>
      {children}
    </div>
  )
}
