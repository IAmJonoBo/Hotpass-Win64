import { useEffect, useMemo, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { Activity, AlertTriangle, CheckCircle2, Clock, ListChecks, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import type { ImportProfile } from '@/types'
import { Badge } from '@/components/ui/badge'
import { cn, formatDuration } from '@/lib/utils'

type ImportStageId = 'queued' | 'upload-complete' | 'refine-started' | 'completed' | 'failed'
type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface LiveProcessingSnapshot {
  id: string
  label?: string
  status?: JobStatus | null
  stage?: ImportStageId | null
  startedAt?: string | null
  updatedAt?: string | null
  completedAt?: string | null
  logs?: string[]
  error?: string | null
  metadata?: Record<string, unknown>
}

export interface LiveProcessingWidgetProps {
  job: LiveProcessingSnapshot | null
  profile?: ImportProfile | null
  workbookName?: string | null
  sheetCount?: number | null
  totalRows?: number | null
  refreshIntervalMs?: number
}

const STAGE_PROGRESS: Record<ImportStageId, number> = {
  queued: 0,
  'upload-complete': 0.35,
  'refine-started': 0.75,
  completed: 1,
  failed: 1,
}

const STATUS_VARIANT: Record<JobStatus, string> = {
  queued: 'border-yellow-500/40 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
  running: 'border-blue-500/40 bg-blue-500/10 text-blue-600 dark:text-blue-300',
  succeeded: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  failed: 'border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400',
}

const FALLBACK_INTERVAL = 300

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const formatNumber = (value: number | undefined | null) =>
  Number.isFinite(value) ? value!.toLocaleString() : '—'

export function LiveProcessingWidget({
  job,
  profile,
  workbookName,
  sheetCount,
  totalRows,
  refreshIntervalMs = FALLBACK_INTERVAL,
}: LiveProcessingWidgetProps) {
  const logs = job?.logs ?? []
  const status: JobStatus = job?.status ?? 'queued'
  const stage: ImportStageId = job?.stage ?? 'queued'

  const [now, setNow] = useState(() => Date.now())

  const startedAtMs = job?.startedAt ? Date.parse(job.startedAt) : null
  const completedAtMs = job?.completedAt ? Date.parse(job.completedAt) : null

  useEffect(() => {
    if (!startedAtMs || Number.isNaN(startedAtMs)) {
      return
    }
    if ((status === 'succeeded' || status === 'failed') && completedAtMs && !Number.isNaN(completedAtMs)) {
      setNow(completedAtMs)
      return
    }
    const interval = window.setInterval(() => {
      setNow(Date.now())
    }, Math.min(Math.max(refreshIntervalMs, 200), 500))
    return () => window.clearInterval(interval)
  }, [startedAtMs, completedAtMs, status, refreshIntervalMs])

  const metadataSheets = useMemo(() => {
    if (!isRecord(job?.metadata)) return []
    const profileMeta = job?.metadata?.profile
    if (isRecord(profileMeta) && Array.isArray(profileMeta.sheets)) {
      return profileMeta.sheets
        .filter(isRecord)
        .map(sheet => ({
          name: typeof sheet.name === 'string' ? sheet.name : 'Sheet',
          rows: typeof sheet.rows === 'number' ? sheet.rows : 0,
        }))
    }
    if (Array.isArray(job?.metadata?.sheets)) {
      return job.metadata.sheets
        .filter(isRecord)
        .map(sheet => ({
          name: typeof sheet.name === 'string' ? sheet.name : 'Sheet',
          rows: typeof sheet.rows === 'number' ? sheet.rows : 0,
        }))
    }
    return []
  }, [job?.metadata])

  const computedSheetCount =
    sheetCount ??
    profile?.sheets?.length ??
    (metadataSheets.length > 0 ? metadataSheets.length : null)

  const computedTotalRows =
    totalRows ??
    profile?.sheets?.reduce((acc, sheet) => acc + (typeof sheet.rows === 'number' ? sheet.rows : 0), 0) ??
    (metadataSheets.length > 0
      ? metadataSheets.reduce((acc, sheet) => acc + sheet.rows, 0)
      : null)

  const rowStats = useMemo(() => {
    let latestLoggedRows = 0
    const rowPattern = /(\d[\d,]*)\s+(rows?|records?)\s+(processed|cleaned|normalized)/i
    logs.forEach(line => {
      const match = rowPattern.exec(line)
      if (match) {
        const value = Number.parseInt(match[1].replace(/,/g, ''), 10)
        if (Number.isFinite(value)) {
          latestLoggedRows = Math.max(latestLoggedRows, value)
        }
      }
    })
    const metadataRows =
      isRecord(job?.metadata) && typeof job?.metadata?.rowsProcessed === 'number'
        ? job.metadata.rowsProcessed
        : 0

    const total = typeof computedTotalRows === 'number' ? Math.max(computedTotalRows, 0) : null
    const progressFallback = total != null
      ? Math.round(total * (STAGE_PROGRESS[stage] ?? 0))
      : 0
    const processed = Math.min(
      total ?? Number.MAX_SAFE_INTEGER,
      Math.max(latestLoggedRows, metadataRows, progressFallback),
    )

    return {
      processed,
      total,
      percent: total ? Math.min(100, Math.round((processed / total) * 100)) : Math.round((STAGE_PROGRESS[stage] ?? 0) * 100),
    }
  }, [computedTotalRows, job?.metadata, logs, stage])

  const autoFixCount = useMemo(() => {
    const autoFixPattern = /\bauto[-\s]?fix(ed|es|ing)?\b/i
    const logMatches = logs.reduce((acc, line) => acc + (autoFixPattern.test(line) ? 1 : 0), 0)
    const metaValue =
      isRecord(job?.metadata) && typeof job?.metadata?.autofixes === 'number'
        ? job.metadata.autofixes
        : 0
    return Math.max(metaValue, logMatches)
  }, [job?.metadata, logs])

  const errorCount = useMemo(() => {
    const errorPattern = /\b(error|failed|exception|traceback)\b/i
    const logMatches = logs.reduce((acc, line) => acc + (errorPattern.test(line) ? 1 : 0), 0)
    const metaValue =
      isRecord(job?.metadata) && typeof job?.metadata?.errors === 'number'
        ? job.metadata.errors
        : 0
    const jobError = job?.error ? 1 : 0
    return Math.max(metaValue, logMatches + jobError)
  }, [job?.metadata, logs, job?.error])

  const elapsedSeconds =
    startedAtMs && !Number.isNaN(startedAtMs)
      ? Math.max(
          0,
          Math.round(
            (((status === 'succeeded' || status === 'failed') && completedAtMs && !Number.isNaN(completedAtMs)
              ? completedAtMs
              : now) - startedAtMs) / 1000,
          ),
        )
      : 0

  const lastUpdatedLabel =
    job?.updatedAt && !Number.isNaN(Date.parse(job.updatedAt))
      ? formatDistanceToNow(new Date(job.updatedAt), { addSuffix: true })
      : job?.startedAt
        ? formatDistanceToNow(new Date(job.startedAt), { addSuffix: true })
        : null

  const effectiveWorkbook =
    workbookName ||
    (profile?.workbook ? String(profile.workbook) : null) ||
    (isRecord(job?.metadata) && typeof job.metadata?.workbook === 'string'
      ? String(job.metadata.workbook)
      : null) ||
    job?.label ||
    job?.id

  const statusVariant = STATUS_VARIANT[status] ?? STATUS_VARIANT.running

  const TrendIcon = rowStats.percent >= 95 ? CheckCircle2 : rowStats.percent >= 70 ? TrendingUp : TrendingDown
  const trendLabel =
    rowStats.percent >= 95 ? 'Healthy throughput' : rowStats.percent >= 70 ? 'On track' : 'Investigate'

  return (
    <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">Live processing</p>
          <p className="text-xs text-muted-foreground">
            Tracking the current Hotpass refine session in real time. Updated every{' '}
            {Math.round(Math.min(Math.max(refreshIntervalMs, 200), 500))} ms.
          </p>
        </div>
        <Badge variant="outline" className={cn('px-3 py-1 text-xs font-semibold', statusVariant)}>
          {status === 'succeeded'
            ? 'Completed'
            : status === 'failed'
              ? 'Failed'
              : status === 'running'
                ? 'Running'
                : 'Queued'}
        </Badge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Workbook</p>
          <p className="mt-1 truncate text-sm font-medium text-foreground" title={effectiveWorkbook ?? undefined}>
            {effectiveWorkbook ?? '—'}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Sheets</p>
          <p className="mt-1 flex items-center gap-2 text-sm font-medium text-foreground">
            <Sparkles className="h-4 w-4 text-primary" />
            {computedSheetCount != null ? computedSheetCount : '—'}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Rows processed</p>
          <p className="mt-1 text-sm font-medium text-foreground">
            {formatNumber(rowStats.processed)}
            {rowStats.total != null ? (
              <span className="text-xs text-muted-foreground"> / {formatNumber(rowStats.total)}</span>
            ) : null}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Session timer</p>
          <p className="mt-1 flex items-center gap-2 text-sm font-medium text-foreground">
            <Clock className="h-4 w-4 text-primary" />
            {elapsedSeconds > 0 ? formatDuration(elapsedSeconds) : '—'}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Autofixes</p>
          <p className="mt-1 flex items-center gap-2 text-sm font-medium text-foreground">
            <ListChecks className="h-4 w-4 text-emerald-500" />
            {formatNumber(autoFixCount)}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Errors surfaced</p>
          <p className="mt-1 flex items-center gap-2 text-sm font-medium text-foreground">
            <AlertTriangle className={cn('h-4 w-4', errorCount > 0 ? 'text-rose-500' : 'text-muted-foreground')} />
            {formatNumber(errorCount)}
          </p>
        </div>
        <div className="rounded-xl border border-border/60 bg-background/80 p-3 sm:col-span-2 lg:col-span-2">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">Throughput health</p>
          <div className="mt-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <TrendIcon className="h-4 w-4 text-primary" />
            {trendLabel} · {rowStats.percent}%
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-muted">
            <div
              className={cn(
                'h-2 rounded-full transition-all',
                rowStats.percent >= 90
                  ? 'bg-emerald-500'
                  : rowStats.percent >= 70
                    ? 'bg-blue-500'
                    : 'bg-amber-500',
              )}
              style={{ width: `${Math.min(100, Math.max(0, rowStats.percent))}%` }}
            />
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Activity className="h-3 w-3" />
          Stage {stage.replace('-', ' ')}
        </span>
        {lastUpdatedLabel && (
          <>
            <span aria-hidden="true">•</span>
            <span>Last update {lastUpdatedLabel}</span>
          </>
        )}
        {job?.id && (
          <>
            <span aria-hidden="true">•</span>
            <span>
              Job {job.id.slice(0, 8)}
            </span>
          </>
        )}
        {job?.error && (
          <>
            <span aria-hidden="true">•</span>
            <span className="inline-flex items-center gap-1 text-rose-500">
              <AlertTriangle className="h-3 w-3" />
              {job.error}
            </span>
          </>
        )}
        {logs.length > 0 && (
          <>
            <span aria-hidden="true">•</span>
            <span>{logs.length} log lines captured</span>
          </>
        )}
      </div>
    </div>
  )
}
