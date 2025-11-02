/**
 * Dashboard Page
 *
 * Shows today's and last 24h Hotpass runs with status, duration, and links to lineage.
 * Integrates with both Prefect (flow runs) and Marquez (job runs).
 */

import { useQuery } from '@tanstack/react-query'
import { Link, useOutletContext } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { Activity, Clock, GitBranch, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiBanner } from '@/components/feedback/ApiBanner'
import { cn, formatDuration, getStatusColor } from '@/lib/utils'
import { prefectApi, mockPrefectData } from '@/api/prefect'
import { useHILApprovals } from '@/store/hilStore'
import { LiveRefinementPanel } from '@/components/refinement/LiveRefinementPanel'
import { PowerTools } from '@/components/powertools/PowerTools'
import { DatasetImportPanel } from '@/components/import/DatasetImportPanel'
import { useLineageTelemetry, jobHasHotpassFacet } from '@/hooks/useLineageTelemetry'

interface OutletContext {
  openAssistant: (message?: string) => void
}

export function Dashboard() {
  const { openAssistant } = useOutletContext<OutletContext>()

  // Fetch Prefect flow runs from last 24h
  const flowRunsQuery = useQuery({
    queryKey: ['flowRuns'],
    queryFn: () => prefectApi.getFlowRuns({ limit: 50 }),
    retry: 1,
  })
  const flowRuns = flowRunsQuery.data ?? mockPrefectData.flowRuns
  const isLoadingPrefect = flowRunsQuery.isLoading
  const prefectError = flowRunsQuery.error instanceof Error ? flowRunsQuery.error : null

  // Fetch HIL approvals
  const { data: hilApprovals = {} } = useHILApprovals()

  const {
    data: lineageTelemetry,
    error: telemetryError,
    isFetching: isFetchingTelemetry,
  } = useLineageTelemetry()

  // Helper to get HIL status badge
  const getHILStatusBadge = (runId: string) => {
    const approval = hilApprovals[runId]
    if (!approval) {
      return (
        <Badge variant="outline" className="text-gray-600 dark:text-gray-400">
          <AlertCircle className="h-3 w-3 mr-1" />
          None
        </Badge>
      )
    }

    switch (approval.status) {
      case 'approved':
        return (
          <Badge variant="outline" className="text-green-600 dark:text-green-400">
            <CheckCircle className="h-3 w-3 mr-1" />
            Approved
          </Badge>
        )
      case 'rejected':
        return (
          <Badge variant="outline" className="text-red-600 dark:text-red-400">
            <XCircle className="h-3 w-3 mr-1" />
            Rejected
          </Badge>
        )
      case 'waiting':
        return (
          <Badge variant="outline" className="text-yellow-600 dark:text-yellow-400">
            <Clock className="h-3 w-3 mr-1" />
            Waiting
          </Badge>
        )
      default:
        return null
    }
  }

  // Note: Marquez jobs could be fetched here for lineage links if needed
  // const { data: marquezJobs = [] } = useQuery({ ... })

  // Filter runs from last 24 hours
  const last24Hours = Date.now() - 24 * 60 * 60 * 1000
  const recentRuns = flowRuns.filter(run => {
    const runTime = new Date(run.created).getTime()
    return runTime >= last24Hours
  })

  // Calculate summary stats
  const totalRuns = recentRuns.length
  const completedRuns = recentRuns.filter(r => r.state_type === 'COMPLETED').length
  const failedRuns = recentRuns.filter(r => r.state_type === 'FAILED').length
  const runningRuns = recentRuns.filter(r => r.state_type === 'RUNNING').length

  const latestSpreadsheets = recentRuns.slice(0, 50).map((run) => {
    const params = run.parameters ?? {}
    const hil = hilApprovals[run.id]
    return {
      id: run.id,
      name: String(params.input_dir || params.source || run.name || 'Unknown input'),
      status: run.state_name,
      geDocs: String(params.data_docs_url || '/dist/data-docs/index.html'),
      notes: hil?.comment || '-',
      run,
    }
  })

  const suggestedBackfills = (lineageTelemetry?.jobs || [])
    .filter((job) => !jobHasHotpassFacet(job))
    .slice(0, 5)
    .map((job) => ({
      id: `backfill-${job.name}`,
      name: `${job.name} (lineage)` ,
      status: 'Needs provenance',
      geDocs: '#',
      notes: 'Missing hotpass lineage facets',
      run: null,
    }))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Monitor pipeline runs, track performance, and explore data lineage
        </p>
      </div>

      <DatasetImportPanel
        flowRuns={flowRuns}
        hilApprovals={hilApprovals}
        isLoadingRuns={isLoadingPrefect}
        onOpenAssistant={openAssistant}
      />

      {prefectError && (
        <ApiBanner
          variant="error"
          title="Prefect API unreachable"
          description="Live run data is temporarily unavailable. Showing cached mock data until the connection recovers."
          badge="fallback"
        />
      )}

      {telemetryError && (
        <ApiBanner
          variant="warning"
          title="Lineage telemetry degraded"
          description={telemetryError instanceof Error ? telemetryError.message : 'The telemetry probe failed to refresh. Historical insights may be stale.'}
        />
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoadingPrefect ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-20" />
                <Skeleton className="h-4 w-24" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">{totalRuns}</div>
                <p className="text-xs text-muted-foreground">Last 24 hours</p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <Badge variant="outline" className="bg-green-500/10 text-green-600 dark:text-green-400">
              ✓
            </Badge>
          </CardHeader>
          <CardContent>
            {isLoadingPrefect ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-4 w-28" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">{completedRuns}</div>
                <p className="text-xs text-muted-foreground">
                  {totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0}% success rate
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <Badge variant="outline" className="bg-red-500/10 text-red-600 dark:text-red-400">
              ✗
            </Badge>
          </CardHeader>
          <CardContent>
            {isLoadingPrefect ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-4 w-28" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">{failedRuns}</div>
                <p className="text-xs text-muted-foreground">
                  {failedRuns > 0 ? 'Needs attention' : 'All good'}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400">
              ⟳
            </Badge>
          </CardHeader>
          <CardContent>
            {isLoadingPrefect ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-4 w-20" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold">{runningRuns}</div>
                <p className="text-xs text-muted-foreground">In progress</p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Live Refinement Panel */}
      <Card>
        <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Lineage Telemetry
            </CardTitle>
            <CardDescription>
              Snapshot of Marquez activity feeding the telemetry strip. Updates every minute.
            </CardDescription>
          </div>
          {isFetchingTelemetry && <span className="text-xs text-muted-foreground">Refreshing…</span>}
        </CardHeader>
        <CardContent>
          {isFetchingTelemetry && !lineageTelemetry ? (
            <div className="grid gap-3 md:grid-cols-3">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Jobs Today</div>
                <div className="mt-2 text-2xl font-semibold">
                  {lineageTelemetry?.jobsToday ?? 0}
                </div>
              </div>
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Failed Today</div>
                <div className="mt-2 text-2xl font-semibold text-red-600 dark:text-red-400">
                  {lineageTelemetry?.failedToday ?? 0}
                </div>
              </div>
              <div className="rounded-2xl border border-border/60 p-4">
                <div className="text-xs uppercase tracking-wide text-muted-foreground">Incomplete Facets</div>
                <div className="mt-2 text-2xl font-semibold text-yellow-700 dark:text-yellow-400">
                  {lineageTelemetry?.incompleteFacets ?? 0}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <LiveRefinementPanel />

      {/* Power Tools */}
      <PowerTools onOpenAssistant={() => openAssistant()} />

      {/* Latest Spreadsheets */}
      <Card>
        <CardHeader>
          <CardTitle>Latest 50 Spreadsheets</CardTitle>
          <CardDescription>
            Pipeline inputs with Great Expectations documentation and operator notes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>GE Docs</TableHead>
                <TableHead>Operator Notes</TableHead>
                <TableHead className="text-right">Last Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoadingPrefect
                ? Array.from({ length: 5 }).map((_, index) => (
                    <TableRow key={`spreadsheets-skeleton-${index}`}>
                      <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                      <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-24" /></TableCell>
                    </TableRow>
                  ))
                : [...latestSpreadsheets, ...suggestedBackfills].map((entry) => (
                    <TableRow key={entry.id} className={entry.run ? undefined : 'bg-yellow-500/10'}>
                      <TableCell className="font-medium">
                        {entry.name}
                        {!entry.run && (
                          <Badge variant="outline" className="ml-2 text-xs text-yellow-700 border-yellow-500/50">
                            Suggested backfill
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn(getStatusColor(entry.status))}>
                          {entry.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {entry.geDocs && entry.geDocs !== '#' ? (
                          <a href={entry.geDocs} className="text-primary hover:underline" target="_blank" rel="noreferrer">
                            View Docs
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground">Not published</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {entry.notes}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        {entry.run?.start_time ? new Date(entry.run.start_time).toLocaleString() : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Recent Runs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Pipeline Runs</CardTitle>
              <CardDescription>
                Latest executions with status and performance metrics
              </CardDescription>
            </div>
            <div className="text-xs text-muted-foreground">
              Last updated: {formatDistanceToNow(new Date(), { addSuffix: true })}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoadingPrefect ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>HIL Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 6 }).map((_, index) => (
                  <TableRow key={`runs-skeleton-${index}`}>
                    <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                    <TableCell className="text-right"><Skeleton className="ml-auto h-4 w-24" /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : recentRuns.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-sm text-muted-foreground">No runs in the last 24 hours</div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>HIL Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentRuns.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="font-medium">
                      <Link
                        to={`/runs/${run.id}`}
                        className="hover:underline flex items-center gap-2"
                      >
                        {run.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={cn(getStatusColor(run.state_type))}
                      >
                        {run.state_name}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {getHILStatusBadge(run.id)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {run.start_time ? (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDistanceToNow(new Date(run.start_time), { addSuffix: true })}
                        </span>
                      ) : (
                        <span>Not started</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {run.total_run_time ? (
                        formatDuration(run.total_run_time)
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {run.tags && run.tags.length > 0 ? (
                        <Badge variant="secondary">{run.tags[0]}</Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/runs/${run.id}`}
                          className="text-xs text-primary hover:underline"
                        >
                          Details
                        </Link>
                        <Link
                          to="/lineage"
                          className="text-xs text-primary hover:underline flex items-center gap-1"
                        >
                          <GitBranch className="h-3 w-3" />
                          Lineage
                        </Link>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
