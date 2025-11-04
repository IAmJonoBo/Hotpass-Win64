import { useEffect, useMemo, useRef, useState } from 'react'
import type { ComponentType } from 'react'
import { formatDistanceToNow } from 'date-fns'
import {
  Activity,
  Atom,
  BadgeCheck,
  Beaker,
  Database,
  MessageSquare,
  RefreshCw,
  Sparkles,
  Wand2,
  XCircle,
  Clock,
  Info,
  ServerCog,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiBanner } from '@/components/feedback/ApiBanner'
import { cn } from '@/lib/utils'
import { clampText } from '@/lib/security'
import { usePipelineRuns } from '@/hooks/usePipelineRuns'
import type { PipelineAction, PipelineRun } from '@/types'

type PanelTab = 'all' | PipelineAction

const HIGHLIGHT_WINDOW_MS = 2_000
const CLEANUP_INTERVAL = 1_000
const MAX_FEEDBACK_LENGTH = 500
const MAX_ROWS = 30

const TAB_CONFIG: Array<{
  id: PanelTab
  label: string
  description: string
  icon: ComponentType<{ className?: string }>
}> = [
  { id: 'all', label: 'All activity', description: 'Latest refinement, normalisation, enrichment, QA', icon: Activity },
  { id: 'refine', label: 'Refinement', description: 'Cleaning & standardisation', icon: Sparkles },
  { id: 'normalize', label: 'Normalisation', description: 'Schema harmonisation & backfills', icon: Atom },
  { id: 'backfill', label: 'Backfilling', description: 'Historical data repair tasks', icon: Database },
  { id: 'enrich', label: 'Enrichment', description: 'External data add-ons', icon: Beaker },
  { id: 'qa', label: 'QA', description: 'Quality gates & validation', icon: BadgeCheck },
  { id: 'contracts', label: 'Contracts', description: 'Data contracts & governance', icon: ServerCog },
  { id: 'other', label: 'Other', description: 'Miscellaneous command runs', icon: Wand2 },
]

const STATUS_BADGE_VARIANT: Record<PipelineRun['status'], { label: string; className: string; icon: ComponentType<{ className?: string }> }> = {
  completed: { label: 'Completed', className: 'text-green-600 dark:text-green-400', icon: BadgeCheck },
  running: { label: 'Running', className: 'text-primary', icon: RefreshCw },
  failed: { label: 'Failed', className: 'text-red-600 dark:text-red-400', icon: XCircle },
  unknown: { label: 'Unknown', className: 'text-muted-foreground', icon: Info },
}

const SOURCE_BADGE: Record<PipelineRun['source'], { label: string; className: string }> = {
  prefect: { label: 'Prefect', className: 'bg-blue-500/10 text-blue-600 dark:text-blue-300' },
  job: { label: 'Local job', className: 'bg-purple-500/10 text-purple-600 dark:text-purple-300' },
}

const ACTION_BADGE: Record<PipelineAction, { label: string; className: string }> = {
  refine: { label: 'Refine', className: 'bg-primary/10 text-primary' },
  normalize: { label: 'Normalize', className: 'bg-amber-500/10 text-amber-600 dark:text-amber-300' },
  backfill: { label: 'Backfill', className: 'bg-sky-500/10 text-sky-600 dark:text-sky-300' },
  enrich: { label: 'Enrich', className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300' },
  qa: { label: 'QA', className: 'bg-rose-500/10 text-rose-600 dark:text-rose-300' },
  contracts: { label: 'Contracts', className: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-300' },
  other: { label: 'Other', className: 'bg-muted/60 text-muted-foreground' },
}

const getStatusIcon = (status: PipelineRun['status']) => {
  const variant = STATUS_BADGE_VARIANT[status] ?? STATUS_BADGE_VARIANT.unknown
  const Icon = variant.icon
  const extraClass = status === 'running' ? 'animate-spin' : ''
  return <Icon className={cn('h-4 w-4', variant.className, extraClass)} />
}

const formatRelative = (value?: string | null) => {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return formatDistanceToNow(parsed, { addSuffix: true })
}

const filterRunsByTab = (runs: PipelineRun[], tab: PanelTab) => {
  if (tab === 'all') return runs
  return runs.filter(run => run.action === tab)
}

const summariseRuns = (runs: PipelineRun[]) => {
  return runs.reduce(
    (acc, run) => {
      acc.total += 1
      acc.status[run.status] = (acc.status[run.status] ?? 0) + 1
      acc.action[run.action] = (acc.action[run.action] ?? 0) + 1
      return acc
    },
    {
      total: 0,
      status: {} as Record<string, number>,
      action: {} as Record<string, number>,
    },
  )
}

const PIPELINE_REFRESH_SECONDS = 15

export interface PipelineActivityPanelProps {
  className?: string
}

export function PipelineActivityPanel({ className }: PipelineActivityPanelProps) {
  const [activeTab, setActiveTab] = useState<PanelTab>('all')
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string | undefined>>({})
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [, setHighlightTick] = useState(0)
  const highlightRef = useRef<Record<string, number>>({})
  const lastVersionRef = useRef<Record<string, string | null>>({})

  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = usePipelineRuns()

  const runs = useMemo(() => (data?.runs ?? []).slice(0, MAX_ROWS), [data])
  const summary = useMemo(() => summariseRuns(runs), [runs])
  const filteredRuns = useMemo(() => filterRunsByTab(runs, activeTab), [runs, activeTab])

  useEffect(() => {
    let cancelled = false
    async function initCsrf() {
      try {
        const response = await fetch('/telemetry/operator-feedback/csrf', {
          method: 'GET',
          credentials: 'include',
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) throw new Error(`Failed to initialise CSRF token (${response.status})`)
        const payload = (await response.json()) as { token?: string }
        if (!cancelled) {
          setCsrfToken(payload.token ?? null)
        }
      } catch (csrfError) {
        console.warn('[pipeline-activity] Unable to load CSRF token', csrfError)
        if (!cancelled) {
          setCsrfToken(null)
        }
      }
    }
    void initCsrf()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const now = Date.now()
    const updatedHighlightMap = { ...highlightRef.current }
    const latestVersionMap = { ...lastVersionRef.current }

    runs.forEach((run) => {
      const versionKey = `${run.id}:${run.updatedAt ?? ''}`
      if (latestVersionMap[run.id] !== versionKey) {
        latestVersionMap[run.id] = versionKey
        updatedHighlightMap[run.id] = now
      }
    })

    highlightRef.current = updatedHighlightMap
    lastVersionRef.current = latestVersionMap
  }, [runs])

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      let mutated = false
      const next = { ...highlightRef.current }
      Object.entries(next).forEach(([id, timestamp]) => {
        if (now - timestamp > HIGHLIGHT_WINDOW_MS) {
          mutated = true
          delete next[id]
        }
      })
      if (mutated) {
        highlightRef.current = next
        setHighlightTick(prev => (prev + 1) % Number.MAX_SAFE_INTEGER)
      }
    }, CLEANUP_INTERVAL)
    return () => clearInterval(interval)
  }, [])

  const handleFeedbackSubmit = async (runId: string) => {
    const rawFeedback = feedback[runId]
    const sanitised = clampText(rawFeedback || '', MAX_FEEDBACK_LENGTH).trim()
    if (!sanitised || !csrfToken || feedbackErrors[runId]) return

    try {
      const response = await fetch('/telemetry/operator-feedback', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({
          rowId: runId,
          feedback: sanitised,
          metadata: {
            submittedAt: new Date().toISOString(),
            runId,
          },
        }),
      })
      if (!response.ok) throw new Error(`Feedback submission failed (${response.status})`)
    } catch (submitError) {
      console.error('[pipeline-activity] Failed to submit feedback', submitError)
      setFeedbackErrors(prev => ({ ...prev, [runId]: 'Could not submit feedback. Please retry.' }))
      return
    }

    setFeedback(prev => ({ ...prev, [runId]: '' }))
    setFeedbackErrors(prev => ({ ...prev, [runId]: undefined }))
    setExpandedRun(null)
  }

  const getRowHighlight = (runId: string) => {
    const timestamp = highlightRef.current[runId]
    if (!timestamp) return false
    return Date.now() - timestamp <= HIGHLIGHT_WINDOW_MS
  }

  const renderStatusBadge = (run: PipelineRun) => {
    const variant = STATUS_BADGE_VARIANT[run.status] ?? STATUS_BADGE_VARIANT.unknown
    return (
      <Badge variant="outline" className={cn('gap-1 capitalize', variant.className)}>
        {getStatusIcon(run.status)}
        {variant.label}
      </Badge>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Pipeline Activity</CardTitle>
            <CardDescription>
              Recent Hotpass runs across refinement, normalisation, enrichment, QA, and contracts
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-300">
              Live (Polling {PIPELINE_REFRESH_SECONDS}s)
            </Badge>
            {data?.lastUpdated && (
              <span>
                Last sync {formatRelative(data.lastUpdated)}
              </span>
            )}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => refetch()}
              disabled={isFetching}
              aria-label="Refresh pipeline activity"
            >
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {TAB_CONFIG.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors',
                  isActive
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background text-muted-foreground hover:border-primary/60 hover:text-foreground',
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="font-medium">{tab.label}</span>
                <span className="hidden sm:inline text-muted-foreground/80">{tab.description}</span>
              </button>
            )
          })}
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
            <div className="text-muted-foreground">Total (last {runs.length} entries)</div>
            <div className="text-lg font-semibold">{summary.total}</div>
          </div>
          <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
            <div className="text-muted-foreground flex items-center gap-1">
              <RefreshCw className="h-3 w-3" /> Running
            </div>
            <div className="text-lg font-semibold">{summary.status.running ?? 0}</div>
          </div>
          <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
            <div className="text-muted-foreground flex items-center gap-1">
              <BadgeCheck className="h-3 w-3" /> Completed
            </div>
            <div className="text-lg font-semibold">{summary.status.completed ?? 0}</div>
          </div>
          <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs">
            <div className="text-muted-foreground flex items-center gap-1">
              <XCircle className="h-3 w-3" /> Failed
            </div>
            <div className="text-lg font-semibold">{summary.status.failed ?? 0}</div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {error instanceof Error && (
          <ApiBanner
            variant="error"
            title="Unable to load latest pipeline runs"
            description={error.message}
            badge="degraded"
          />
        )}

        {isLoading ? (
          <div className="text-sm text-muted-foreground">
            Fetching latest runs from Prefect and local jobs…
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            No pipeline activity found for this filter window. Try adjusting the tab or check again shortly.
          </div>
        ) : (
          <div className="rounded-lg border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Process</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Timeline</TableHead>
                  <TableHead>Profile & notes</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRuns.map((run) => {
                  const highlight = getRowHighlight(run.id)
                  const actionBadge = ACTION_BADGE[run.action]
                  const sourceBadge = SOURCE_BADGE[run.source]
                  const started = formatRelative(run.startedAt)
                  const finished = formatRelative(run.finishedAt)

                  return (
                    <TableRow key={run.id} className={cn(highlight && 'bg-primary/5 transition-colors')}>
                      <TableCell>
                        <div className="flex flex-col gap-1 text-sm">
                          <span className="font-medium truncate">{run.runName ?? run.id}</span>
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <Badge variant="outline" className={cn('capitalize', actionBadge.className)}>
                              {actionBadge.label}
                            </Badge>
                            {sourceBadge && (
                              <Badge variant="outline" className={cn('capitalize', sourceBadge.className)}>
                                {sourceBadge.label}
                              </Badge>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>{renderStatusBadge(run)}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <div className="flex flex-col">
                          <span>Started {started}</span>
                          {run.status === 'completed' && (
                            <span>Completed {finished}</span>
                          )}
                          {run.status === 'running' && (
                            <span className="flex items-center gap-1 text-primary">
                              <Clock className="h-3 w-3" /> In progress
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        <div className="flex flex-col gap-1">
                          {run.profile && (
                            <span className="text-xs uppercase tracking-wide text-muted-foreground/80">
                              Profile {run.profile}
                            </span>
                          )}
                          <span>{run.notes ?? '—'}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {run.dataDocsUrl && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => window.open(run.dataDocsUrl, '_blank', 'noreferrer')}
                            >
                              Docs
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpandedRun(prev => (prev === run.id ? null : run.id))}
                          >
                            <MessageSquare className="h-4 w-4" />
                            <span className="sr-only">Toggle feedback</span>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}

        {filteredRuns.map((run) => (
          expandedRun === run.id && (
            <div key={`feedback-${run.id}`} className="rounded-lg border bg-muted/40 p-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Operator feedback for {run.runName ?? run.id}</h4>
                <span className="text-xs text-muted-foreground">Max {MAX_FEEDBACK_LENGTH} characters</span>
              </div>
              <Input
                className="mt-3"
                value={feedback[run.id] ?? ''}
                onChange={(event) => {
                  const raw = event.target.value
                  const sanitised = clampText(raw, MAX_FEEDBACK_LENGTH)
                  setFeedback(prev => ({ ...prev, [run.id]: sanitised }))
                  setFeedbackErrors(prev => ({ ...prev, [run.id]: undefined }))
                }}
                placeholder="Share context for downstream reviewers"
              />
              {feedbackErrors[run.id] && (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">{feedbackErrors[run.id]}</p>
              )}
              <div className="mt-3 flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setExpandedRun(null)}>
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleFeedbackSubmit(run.id)}
                  disabled={!feedback[run.id]}
                >
                  Submit
                </Button>
              </div>
            </div>
          )
        ))}
      </CardContent>
    </Card>
  )
}
