/**
 * Run Details Page
 *
 * Shows detailed information about a specific pipeline run including:
 * - Raw OpenLineage event
 * - Related datasets
 * - QA results from dist/data-docs/ or Prefect
 * - Run parameters and metadata
 */

import { useParams, Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, XCircle, AlertTriangle, Clock, Tag, UserCheck, GitBranch, Loader2, Terminal } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiBanner } from '@/components/feedback/ApiBanner'
import { prefectApi, mockPrefectData } from '@/api/prefect'
import { useLineageTelemetry } from '@/hooks/useLineageTelemetry'
import { cn, formatDuration, getStatusColor } from '@/lib/utils'
import { ApprovalPanel } from '@/components/hil/ApprovalPanel'
import type { QAResult } from '@/types'
import { useAuth } from '@/auth'

interface OutletContext {
  openAssistant: (message?: string) => void
  openHelp: (options?: { topicId?: string; query?: string }) => void
}

interface LogEntry {
  id: string
  message: string
  stream: 'stdout' | 'stderr'
  timestamp?: string | null
  highlight: boolean
}

const MAX_LOG_LINES = 400

export function RunDetails() {
  const { runId } = useParams<{ runId: string }>()
  const { openAssistant } = useOutletContext<OutletContext>()
  const [approvalPanelOpen, setApprovalPanelOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [isStreamingLogs, setIsStreamingLogs] = useState(false)
  const [logError, setLogError] = useState<string | null>(null)
  const highlightTimeoutsRef = useRef<Record<string, number>>({})
  const streamClosedByServerRef = useRef(false)
  const { hasRole } = useAuth()

  const mockRun = mockPrefectData.flowRuns.find(r => r.id === runId)

  // Fetch run details
  const runQuery = useQuery({
    queryKey: ['flowRun', runId],
    queryFn: () => prefectApi.getFlowRun(runId!),
    enabled: !!runId,
    retry: 1,
  })
  const runError = runQuery.error instanceof Error ? runQuery.error : null
  const run = runQuery.data ?? (runError ? mockRun : undefined)
  const isLoading = runQuery.isLoading
  const showSkeleton = isLoading && !run
  const isFallback = Boolean(runError && mockRun)
  const canApprove = hasRole(['approver', 'admin'])
  const shouldAutoOpenApproval = useMemo(() => {
    const value = searchParams.get('hil') ?? searchParams.get('openApproval')
    if (!value) return false
    return value === '1' || value === 'true' || value === 'open'
  }, [searchParams])

  useEffect(() => {
    if (shouldAutoOpenApproval) {
      setApprovalPanelOpen(true)
    }
  }, [shouldAutoOpenApproval])

  const clearHighlightTimeouts = () => {
    Object.values(highlightTimeoutsRef.current).forEach((timeoutId) => window.clearTimeout(timeoutId))
    highlightTimeoutsRef.current = {}
  }

  useEffect(() => {
    clearHighlightTimeouts()
    setLogEntries([])
    setLogError(null)
    streamClosedByServerRef.current = false

    if (!runId) {
      setIsStreamingLogs(false)
      return
    }

    let eventSource: EventSource | null = null

    const parseEventData = (event: MessageEvent<string>) => {
      try {
        return JSON.parse(event.data) as Record<string, unknown>
      } catch (error) {
        console.warn('[run-details] failed to parse log event payload', error)
        return null
      }
    }

    const openStream = () => {
      setIsStreamingLogs(true)
      setLogError(null)

      eventSource = new EventSource(`/api/runs/${encodeURIComponent(runId)}/logs`)

      eventSource.addEventListener('snapshot', (event) => {
        const payload = parseEventData(event as MessageEvent<string>)
        if (!payload || !Array.isArray(payload.logs)) return
        setLogEntries(
          payload.logs
            .map((log, index) => {
              if (!log || typeof log !== 'object') return null
              const safeLog = log as Record<string, unknown>
              return {
                id: `snapshot-${index}-${safeLog.timestamp ?? index}`,
                message: typeof safeLog.message === 'string' ? safeLog.message : '',
                stream: (typeof safeLog.stream === 'string' && safeLog.stream === 'stderr') ? 'stderr' : 'stdout',
                timestamp: typeof safeLog.timestamp === 'string' ? safeLog.timestamp : null,
                highlight: false,
              } satisfies LogEntry
            })
            .filter(Boolean) as LogEntry[],
        )
      })

      eventSource.addEventListener('log', (event) => {
        const payload = parseEventData(event as MessageEvent<string>)
        if (!payload || typeof payload.message !== 'string') {
          return
        }

        const entryId = `log-${Date.now()}-${Math.random().toString(16).slice(2)}`
        const entry: LogEntry = {
          id: entryId,
          message: payload.message,
          stream: typeof payload.stream === 'string' && payload.stream === 'stderr' ? 'stderr' : 'stdout',
          timestamp: typeof payload.timestamp === 'string' ? payload.timestamp : new Date().toISOString(),
          highlight: true,
        }

        setLogEntries((previous) => {
          const next = [...previous, entry]
          if (next.length > MAX_LOG_LINES) {
            next.splice(0, next.length - MAX_LOG_LINES)
          }
          return next
        })

        highlightTimeoutsRef.current[entryId] = window.setTimeout(() => {
          setLogEntries((previous) =>
            previous.map((item) => (item.id === entryId ? { ...item, highlight: false } : item)),
          )
          delete highlightTimeoutsRef.current[entryId]
        }, 180)
      })

      eventSource.addEventListener('finished', () => {
        streamClosedByServerRef.current = true
        setIsStreamingLogs(false)
        eventSource?.close()
      })

      eventSource.onerror = () => {
        eventSource?.close()
        if (!streamClosedByServerRef.current) {
          setLogError('Streaming logs unavailable for this run.')
        }
        setIsStreamingLogs(false)
      }
    }

    try {
      openStream()
    } catch (error) {
      console.error('[run-details] failed to open log stream', error)
      setLogError('Unable to initialise log stream.')
      setIsStreamingLogs(false)
    }

    return () => {
      eventSource?.close()
      clearHighlightTimeouts()
    }
  }, [runId])

  const {
    data: lineageTelemetry,
    error: telemetryError,
    isFetching: isFetchingTelemetry,
  } = useLineageTelemetry()

  // Mock QA results (in production, these would come from dist/data-docs or the run artifacts)
  const mockQAResults: QAResult[] = [
    {
      check: 'Schema Validation',
      status: 'passed',
      message: 'All required columns present',
      details: { columns: 45, validated: 45 },
    },
    {
      check: 'Data Quality',
      status: 'passed',
      message: 'No duplicate records found',
      details: { total_rows: 1234, duplicates: 0 },
    },
    {
      check: 'Completeness',
      status: 'warning',
      message: '2% of records have missing phone numbers',
      details: { total: 1234, missing: 25 },
    },
    {
      check: 'Provenance',
      status: 'passed',
      message: 'All records have provenance metadata',
      details: { tracked: 1234 },
    },
  ]

  if (!run && !showSkeleton) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-lg font-semibold">Run not found</div>
          <p className="text-sm text-muted-foreground mt-2">
            The requested run could not be found.
          </p>
          <Link to="/" className="mt-4 inline-block">
            <Button variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dashboard
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const rawMarquezUrl = import.meta.env.OPENLINEAGE_URL || import.meta.env.VITE_MARQUEZ_API_URL || ''
  const marquezUiBase = rawMarquezUrl.replace(/\/api(?:\/v1)?$/, '')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link to="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
          </div>
          {showSkeleton ? (
            <>
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-40" />
            </>
          ) : (
            <>
              <h1 className="text-3xl font-bold tracking-tight">{run?.name}</h1>
              <p className="text-muted-foreground">Run ID: {run?.id}</p>
            </>
          )}
        </div>
        {showSkeleton ? (
          <Skeleton className="h-10 w-28" />
        ) : run && (
          <Badge
            variant="outline"
            className={cn('text-base px-4 py-2', getStatusColor(run.state_type))}
          >
            {run.state_name}
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-3">
        {showSkeleton ? (
          <Skeleton className="h-9 w-44" />
        ) : (
          <>
            <Button variant="outline" size="sm" disabled={!run}>
              <a
                href={marquezUiBase && run ? `${marquezUiBase}/runs/${encodeURIComponent(run.id)}` : '#'}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1"
              >
                Open in Marquez
              </a>
            </Button>
            <div className="text-xs text-muted-foreground">
              Uses the shared OPENLINEAGE_URL so CLI and UI link to the same namespace.
            </div>
          </>
        )}
      </div>

      {runError && (
        <ApiBanner
          variant="error"
          title="Prefect API unreachable"
          description="Showing cached mock data until the Prefect flow run endpoint is reachable again."
          badge={isFallback ? 'fallback' : undefined}
        />
      )}

      {telemetryError && (
        <ApiBanner
          variant="warning"
          title="Lineage telemetry degraded"
          description={telemetryError instanceof Error ? telemetryError.message : 'Telemetry probes failed. Lineage insights may be stale.'}
        />
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {showSkeleton ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-24" />
                <Skeleton className="h-4 w-32" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {run?.total_run_time ? formatDuration(run.total_run_time) : '-'}
                </div>
                <p className="text-xs text-muted-foreground">
                  {run?.start_time ? new Date(run.start_time).toLocaleString() : 'Not started'}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Flow</CardTitle>
            <Tag className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {showSkeleton ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-24" />
              </div>
            ) : (
              <>
                <div className="text-sm font-medium truncate">{run?.flow_id}</div>
                <p className="text-xs text-muted-foreground">Flow ID</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tags</CardTitle>
          </CardHeader>
          <CardContent>
            {showSkeleton ? (
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-5 w-20" />
              </div>
            ) : (
              <div className="flex flex-wrap gap-1">
                {run?.tags && run.tags.length > 0 ? (
                  run.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground">No tags</span>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">QA Status</CardTitle>
          </CardHeader>
          <CardContent>
            {showSkeleton ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-4 w-28" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {mockQAResults.filter(r => r.status === 'passed').length}/{mockQAResults.length}
                </div>
                <p className="text-xs text-muted-foreground">Checks passed</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Lineage Telemetry
            </CardTitle>
            <CardDescription>Recent Marquez activity that may impact this run&apos;s context.</CardDescription>
          </div>
          {isFetchingTelemetry && <span className="text-xs text-muted-foreground">Refreshing…</span>}
        </CardHeader>
        <CardContent>
          {isFetchingTelemetry && !lineageTelemetry ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase text-muted-foreground">Jobs Today</div>
                <div className="mt-2 text-xl font-semibold">{lineageTelemetry?.jobsToday ?? 0}</div>
              </div>
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase text-muted-foreground">Failed Today</div>
                <div className="mt-2 text-xl font-semibold text-red-600 dark:text-red-400">{lineageTelemetry?.failedToday ?? 0}</div>
              </div>
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase text-muted-foreground">Incomplete Facets</div>
                <div className="mt-2 text-xl font-semibold text-yellow-700 dark:text-yellow-400">{lineageTelemetry?.incompleteFacets ?? 0}</div>
              </div>
            </div>
          )}
      </CardContent>
    </Card>

      {/* QA Results */}
      <Card>
        <CardHeader>
          <CardTitle>Quality Assurance Results</CardTitle>
          <CardDescription>
            Validation checks from the pipeline execution
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Check</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Message</TableHead>
                <TableHead className="text-right">Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {showSkeleton
                ? Array.from({ length: 4 }).map((_, index) => (
                    <TableRow key={`qa-skeleton-${index}`}>
                      <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-64" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-20" /></TableCell>
                    </TableRow>
                  ))
                : mockQAResults.map((result, index) => (
                    <TableRow key={index}>
                      <TableCell className="font-medium">{result.check}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {result.status === 'passed' && (
                            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                          )}
                          {result.status === 'failed' && (
                            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                          )}
                          {result.status === 'warning' && (
                            <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                          )}
                          <Badge
                            variant="outline"
                            className={cn(
                              result.status === 'passed'
                                ? 'text-green-600 dark:text-green-400'
                                : result.status === 'failed'
                                ? 'text-red-600 dark:text-red-400'
                                : 'text-yellow-600 dark:text-yellow-400'
                            )}
                          >
                            {result.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>{result.message}</TableCell>
                      <TableCell className="text-right text-sm text-muted-foreground">
                        {result.details && (
                          <code className="text-xs">
                            {JSON.stringify(result.details).slice(0, 50)}...
                          </code>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Run Parameters */}
      <Card>
        <CardHeader>
          <CardTitle>Run Parameters</CardTitle>
          <CardDescription>
            Configuration and inputs for this execution
          </CardDescription>
        </CardHeader>
        <CardContent>
          {showSkeleton ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <div className="rounded-lg bg-muted p-4">
              <pre className="text-sm overflow-x-auto">
                {JSON.stringify(run?.parameters || {}, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Raw Event Data */}
      <Card>
        <CardHeader>
          <CardTitle>Raw Event Data</CardTitle>
          <CardDescription>
            Complete run metadata from Prefect
          </CardDescription>
        </CardHeader>
        <CardContent>
          {showSkeleton ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="rounded-lg bg-muted p-4">
              <pre className="text-sm overflow-x-auto">
                {JSON.stringify(run, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Terminal className="h-4 w-4" />
              Live Logs
            </CardTitle>
            <CardDescription>Streaming updates from the underlying job runner.</CardDescription>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {isStreamingLogs && (
              <span className="inline-flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                Streaming…
              </span>
            )}
            <span>{logEntries.length} lines</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {logError && (
            <ApiBanner
              variant="warning"
              title="Live logs unavailable"
              description={logError}
            />
          )}
          <div className="max-h-72 overflow-y-auto rounded-2xl border border-border/60 bg-background/95 p-3 font-mono text-xs shadow-inner">
            {logEntries.length === 0 ? (
              <p className="text-muted-foreground">
                {isStreamingLogs ? 'Waiting for logs…' : 'No logs captured for this run yet.'}
              </p>
            ) : (
              logEntries.map((entry) => (
                <div
                  key={entry.id}
                  className={cn(
                    'mb-1 rounded-lg border border-transparent px-2 py-1 transition-colors last:mb-0',
                    entry.highlight && 'border-primary/40 bg-primary/10 shadow-sm',
                  )}
                >
                  <span
                    className={cn(
                      'font-semibold',
                      entry.stream === 'stderr' ? 'text-rose-500' : 'text-muted-foreground',
                    )}
                  >
                    [{entry.stream}]
                  </span>
                  <span className="ml-2 text-foreground">{entry.message}</span>
                  {entry.timestamp && (
                    <span className="ml-2 text-muted-foreground/70">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between gap-2">
        <div className="flex flex-col gap-1">
          <Button
            variant="default"
            disabled={showSkeleton || !run || !canApprove}
            onClick={() => setApprovalPanelOpen(true)}
          >
            <UserCheck className="mr-2 h-4 w-4" />
            Review & Approve
          </Button>
          {!canApprove && !showSkeleton && (
            <p className="text-xs text-muted-foreground">Approver role required.</p>
          )}
        </div>
        <div className="flex gap-2">
          <Link to="/lineage">
            <Button variant="outline" disabled={showSkeleton}>View Lineage</Button>
          </Link>
          <Button disabled={showSkeleton || !run}>Rerun Pipeline</Button>
        </div>
      </div>

      {/* Approval Panel */}
      {run && (
        <ApprovalPanel
          open={approvalPanelOpen}
          onOpenChange={setApprovalPanelOpen}
          run={run}
          qaResults={mockQAResults}
          onOpenAssistant={openAssistant}
          canApprove={canApprove}
        />
      )}
    </div>
  )
}
