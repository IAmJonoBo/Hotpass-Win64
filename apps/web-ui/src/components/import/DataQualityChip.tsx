import { TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'

type Trend = 'up' | 'down' | 'steady'

export interface DataQualityChipProps {
  passRate: number
  trend?: Trend
  windowLabel?: string
  totalRuns?: number
  className?: string
}

const resolveTrend = (trend?: Trend) => {
  switch (trend) {
    case 'up':
      return { Icon: TrendingUp, label: 'Improving', className: 'text-emerald-600 dark:text-emerald-400' }
    case 'down':
      return { Icon: TrendingDown, label: 'Declining', className: 'text-amber-600 dark:text-amber-400' }
    default:
      return { Icon: Minus, label: 'Stable', className: 'text-slate-500 dark:text-slate-300' }
  }
}

const resolveStatusVariant = (passRate: number) => {
  if (passRate >= 0.95) {
    return {
      label: 'Excellent',
      container: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-600 dark:text-emerald-400',
    }
  }
  if (passRate >= 0.85) {
    return {
      label: 'Good',
      container: 'bg-blue-500/10 border-blue-500/40 text-blue-600 dark:text-blue-300',
    }
  }
  if (passRate >= 0.7) {
    return {
      label: 'Watch',
      container: 'bg-amber-500/10 border-amber-500/40 text-amber-600 dark:text-amber-400',
    }
  }
  return {
    label: 'At Risk',
    container: 'bg-rose-500/10 border-rose-500/40 text-rose-600 dark:text-rose-400',
  }
}

export function DataQualityChip({
  passRate,
  trend = 'steady',
  windowLabel,
  totalRuns,
  className,
}: DataQualityChipProps) {
  const rate = Number.isFinite(passRate) ? Math.max(0, Math.min(1, passRate)) : 0
  const displayRate = Math.round(rate * 100)
  const variant = resolveStatusVariant(rate)
  const trendData = resolveTrend(trend)

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        variant.container,
        className,
      )}
    >
      <span className="flex items-center gap-1">
        <span className="font-semibold">{displayRate}% pass</span>
        <span aria-hidden="true" className="text-muted-foreground/80">
          ·
        </span>
        <span>{variant.label}</span>
      </span>
      <span aria-hidden="true" className="text-muted-foreground/60">
        |
      </span>
      <span className={cn('flex items-center gap-1', trendData.className)}>
        <trendData.Icon className="h-3 w-3" />
        {trendData.label}
      </span>
      {typeof totalRuns === 'number' && totalRuns > 0 && (
        <span className="text-muted-foreground/80">
          ({totalRuns} runs{windowLabel ? ` · ${windowLabel}` : ''})
        </span>
      )}
      {!totalRuns && windowLabel && (
        <span className="text-muted-foreground/80">
          {windowLabel}
        </span>
      )}
    </div>
  )
}

