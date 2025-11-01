import { type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

type ApiBannerVariant = 'error' | 'warning' | 'info' | 'success'

const VARIANT_CONFIG: Record<
  ApiBannerVariant,
  { icon: ReactNode; border: string; text: string; badge: string }
> = {
  error: {
    icon: <AlertTriangle className="h-4 w-4" />,
    border: 'border-red-500/40 bg-red-500/10',
    text: 'text-red-600 dark:text-red-400',
    badge: 'bg-red-500/20 text-red-600 dark:text-red-300',
  },
  warning: {
    icon: <ShieldAlert className="h-4 w-4" />,
    border: 'border-yellow-500/40 bg-yellow-500/10',
    text: 'text-yellow-700 dark:text-yellow-400',
    badge: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-300',
  },
  info: {
    icon: <Info className="h-4 w-4" />,
    border: 'border-blue-500/40 bg-blue-500/10',
    text: 'text-blue-700 dark:text-blue-300',
    badge: 'bg-blue-500/20 text-blue-700 dark:text-blue-200',
  },
  success: {
    icon: <CheckCircle2 className="h-4 w-4" />,
    border: 'border-emerald-500/40 bg-emerald-500/10',
    text: 'text-emerald-700 dark:text-emerald-300',
    badge: 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-200',
  },
}

interface ApiBannerProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  description?: string
  variant?: ApiBannerVariant
  action?: ReactNode
  iconOverride?: ReactNode
  badge?: string
  compact?: boolean
}

export function ApiBanner({
  title,
  description,
  variant = 'info',
  action,
  iconOverride,
  badge,
  compact,
  className,
  ...props
}: ApiBannerProps) {
  const config = VARIANT_CONFIG[variant]

  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-3',
        config.border,
        className,
      )}
      {...props}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-1 flex h-6 w-6 items-center justify-center rounded-full', config.badge)}>
          {iconOverride ?? config.icon}
        </div>
        <div className="flex-1 space-y-1">
          <div className={cn('font-semibold text-sm leading-tight', config.text)}>
            {title}
            {badge && (
              <span className="ml-2 rounded-full bg-background/80 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p
              className={cn(
                'text-xs leading-relaxed',
                config.text,
                compact && '!leading-snug',
              )}
            >
              {description}
            </p>
          )}
          {action && <div className="pt-1">{action}</div>}
        </div>
      </div>
    </div>
  )
}
