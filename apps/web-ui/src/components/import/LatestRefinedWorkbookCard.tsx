import { Link } from 'react-router-dom'
import { ArrowUpRight, Clock, FileSpreadsheet, History, Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DataQualityChip } from './DataQualityChip'
import { cn, formatDuration } from '@/lib/utils'

interface LatestRefinedWorkbookCardProps {
  run?: {
    id: string
    name?: string
    state_name?: string
    state_type?: string
    profile?: string
    startedAt?: string
    completedAt?: string
    durationSeconds?: number
    parameters?: Record<string, unknown>
  }
  passRate: number
  totalRuns: number
  windowLabel?: string
  trend?: 'up' | 'down' | 'steady'
  className?: string
}

const resolveRunStatus = (stateType?: string) => {
  const normalised = (stateType ?? '').toLowerCase()
  if (normalised === 'completed') return { label: 'Completed', className: 'text-emerald-600 dark:text-emerald-400' }
  if (normalised === 'running') return { label: 'In Progress', className: 'text-primary' }
  if (normalised === 'failed' || normalised === 'crashed' || normalised === 'cancelled') {
    return { label: 'Failed', className: 'text-rose-600 dark:text-rose-400' }
  }
  return { label: 'Queued', className: 'text-muted-foreground' }
}

const formatRelativeTime = (value?: string) => {
  if (!value) return '—'
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return '—'
  const diffMs = Date.now() - timestamp
  const diffMinutes = Math.round(diffMs / 60_000)
  if (diffMinutes < 1) return 'moments ago'
  if (diffMinutes === 1) return '1 minute ago'
  if (diffMinutes < 60) return `${diffMinutes} minutes ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  const diffDays = Math.round(diffHours / 24)
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
}

export function LatestRefinedWorkbookCard({
  run,
  passRate,
  totalRuns,
  windowLabel,
  trend,
  className,
}: LatestRefinedWorkbookCardProps) {
  if (!run) {
    return (
      <Card className={cn('rounded-3xl border-dashed border-border/60 bg-muted/30', className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            Latest refined workbook
          </CardTitle>
          <CardDescription>
            Once a refine run completes, a summary of the workbook and QA status appears here.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            No completed refine runs detected in the last 24 hours. Upload a workbook from the Import panel to see live results.
          </p>
          <Link to="/imports/wizard" className="inline-flex">
            <Button variant="outline" size="sm">
              Launch Smart Import
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    )
  }

  const status = resolveRunStatus(run.state_type)
  const profile = typeof run.profile === 'string' ? run.profile : undefined
  const workbookName =
    (typeof run.parameters?.input_dir === 'string' && run.parameters.input_dir) ||
    (typeof run.parameters?.source === 'string' && run.parameters.source) ||
    run.name ||
    run.id

  const durationLabel = run.durationSeconds ? formatDuration(run.durationSeconds) : '—'

  return (
    <Card className={cn('rounded-3xl border border-border/80 bg-card/90 shadow-sm', className)}>
      <CardHeader className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <FileSpreadsheet className="h-4 w-4 text-primary" aria-hidden="true" />
            Latest refined workbook
          </CardTitle>
          <Badge variant="outline" className={status.className}>
            {status.label}
          </Badge>
        </div>
        <CardDescription className="flex items-center gap-2 text-xs text-muted-foreground">
          <History className="h-3 w-3" aria-hidden="true" />
          Completed {formatRelativeTime(run.completedAt ?? run.startedAt)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-base font-semibold text-foreground">{workbookName}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {profile && (
              <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[11px] uppercase tracking-wide">
                {profile}
              </Badge>
            )}
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" aria-hidden="true" />
              Duration {durationLabel}
            </span>
            {run.state_name && (
              <span className="inline-flex items-center gap-1 text-muted-foreground/80">
                <Sparkles className="h-3 w-3" aria-hidden="true" />
                {run.state_name}
              </span>
            )}
          </div>
        </div>

        <DataQualityChip
          passRate={passRate}
          trend={trend}
          totalRuns={totalRuns}
          windowLabel={windowLabel}
        />

        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>
            Run ID <span className="font-mono text-foreground">{run.id}</span>
          </span>
          {typeof run.parameters?.data_docs_url === 'string' && (
            <>
              <span aria-hidden="true" className="text-muted-foreground/60">
                ·
              </span>
              <a href={run.parameters.data_docs_url} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">
                Data Docs
              </a>
            </>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Link to={`/runs/${run.id}`}>
            <Button size="sm">
              View run details
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
          {typeof run.parameters?.data_docs_url === 'string' && (
            <a
              href={run.parameters.data_docs_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex"
            >
              <Button size="sm" variant="outline">
                Open data docs
                <ArrowUpRight className="ml-2 h-4 w-4" />
              </Button>
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
