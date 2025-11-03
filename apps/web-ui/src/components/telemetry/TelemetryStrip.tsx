/**
 * Telemetry Strip Component
 *
 * Compact status bar showing environment, agent activity, API health, and failed runs.
 */

import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { Activity, AlertTriangle, CheckCircle, Server, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { prefectApi } from '@/api/prefect'
import { marquezApi } from '@/api/marquez'
import { useLineageTelemetry } from '@/hooks/useLineageTelemetry'

interface TelemetryStripProps {
  className?: string
}

type TelemetryJob = {
  id?: string
  status?: string
  updatedAt?: string
  completedAt?: string
  startedAt?: string
  createdAt?: string
  label?: string
  metadata?: Record<string, unknown>
}

export function TelemetryStrip({ className }: TelemetryStripProps) {
  const environment =
    import.meta.env.HOTPASS_ENVIRONMENT ||
    import.meta.env.VITE_ENVIRONMENT ||
    'local'

  // Check if telemetry is enabled (from localStorage/Admin)
  const telemetryEnabled =
    typeof window !== 'undefined' &&
    localStorage.getItem('hotpass_telemetry_enabled') !== 'false'

  // Fetch recent flow runs to check for failures
  const { data: flowRuns = [] } = useQuery({
    queryKey: ['telemetry-flow-runs'],
    queryFn: async () => {
      try {
        return await prefectApi.getFlowRuns({ limit: 100 })
      } catch (error) {
        console.warn('Telemetry: Failed to fetch flow runs:', error)
        return []
      }
    },
    refetchInterval: 30000, // Refresh every 30 seconds
    enabled: telemetryEnabled,
  })

  // Check Prefect API health
  const { data: prefectHealth, isLoading: prefectLoading } = useQuery({
    queryKey: ['telemetry-prefect-health'],
    queryFn: async () => {
      try {
        await prefectApi.getFlows(1)
        return { status: 'healthy', timestamp: new Date() }
      } catch (error) {
        console.warn('Telemetry: Prefect health check failed:', error)
        return { status: 'error', timestamp: new Date() }
      }
    },
    refetchInterval: 60000, // Check every minute
    enabled: telemetryEnabled,
  })

  // Check Marquez API health
  const { data: marquezHealth, isLoading: marquezLoading } = useQuery({
    queryKey: ['telemetry-marquez-health'],
    queryFn: async () => {
      try {
        await marquezApi.getNamespaces()
        return { status: 'healthy', timestamp: new Date() }
      } catch (error) {
        console.warn('Telemetry: Marquez health check failed:', error)
        return { status: 'error', timestamp: new Date() }
      }
    },
    refetchInterval: 60000, // Check every minute
    enabled: telemetryEnabled,
  })

  const { data: lineageTelemetry } = useLineageTelemetry()
  const { data: jobsPayload = { jobs: [] as TelemetryJob[] } } = useQuery({
    queryKey: ['telemetry-jobs'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/jobs', {
          credentials: 'include',
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) {
          throw new Error(`Failed to fetch jobs (${response.status})`)
        }
        const payload = (await response.json()) as { jobs?: TelemetryJob[] }
        const jobs = Array.isArray(payload?.jobs) ? payload.jobs : []
        return { jobs }
      } catch (error) {
        console.warn('Telemetry: Job fetch failed:', error)
        return { jobs: [] }
      }
    },
    refetchInterval: 30000,
    enabled: telemetryEnabled,
  })

  if (!telemetryEnabled) {
    return null
  }

  // Calculate failed runs in last 30 minutes
  const thirtyMinutesAgo = Date.now() - 30 * 60 * 1000
  const recentFailedRuns = flowRuns.filter(run => {
    const runTime = new Date(run.created).getTime()
    return runTime >= thirtyMinutesAgo && run.state_type === 'FAILED'
  }).length

  const jobs = jobsPayload.jobs ?? []
  const getJobTimestamp = (job: TelemetryJob): number => {
    const candidates = [
      job.updatedAt,
      job.completedAt,
      job.startedAt,
      job.createdAt,
    ]
    for (const candidate of candidates) {
      if (typeof candidate === 'string' || candidate instanceof Date) {
        const value = new Date(candidate).getTime()
        if (!Number.isNaN(value)) {
          return value
        }
      }
    }
    return 0
  }

  const jobFailures = jobs.filter(job => job?.status === 'failed')
  const recentJobFailures = jobFailures.filter(job => getJobTimestamp(job) >= thirtyMinutesAgo)
  const latestJobFailure = jobFailures.reduce<number>((acc, job) => {
    const ts = getJobTimestamp(job)
    return ts > acc ? ts : acc
  }, 0)

  const jobFailureSummary =
    jobFailures.length === 0
      ? 'Healthy'
      : latestJobFailure > 0
        ? `Last failed ${formatDistanceToNow(new Date(latestJobFailure), { addSuffix: true })}`
        : `${jobFailures.length} failures recorded`

  const hasIssues = recentFailedRuns > 0 ||
    prefectHealth?.status === 'error' ||
    marquezHealth?.status === 'error' ||
    (lineageTelemetry?.incompleteFacets ?? 0) > 0 ||
    recentJobFailures.length > 0

  return (
    <div
      className={cn(
        'border-b bg-muted/30 px-6 py-2 text-xs flex items-center justify-between',
        className
      )}
    >
      {/* Left side - Status indicators */}
      <div className="flex items-center gap-4">
        {/* Environment */}
        <div className="flex items-center gap-2">
          <Server className="h-3 w-3 text-muted-foreground" />
          <span className="text-muted-foreground">Environment:</span>
          <Badge variant="outline" className="text-xs">
            {environment}
          </Badge>
        </div>

        {/* Prefect Status */}
        <div className="flex items-center gap-2">
          {prefectLoading ? (
            <Clock className="h-3 w-3 text-muted-foreground animate-spin" />
          ) : prefectHealth?.status === 'healthy' ? (
            <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
          ) : (
            <AlertTriangle className="h-3 w-3 text-red-600 dark:text-red-400" />
          )}
          <span className="text-muted-foreground">Prefect:</span>
          <span className={cn(
            prefectHealth?.status === 'healthy'
              ? 'text-green-600 dark:text-green-400'
              : 'text-red-600 dark:text-red-400'
          )}>
            {prefectHealth?.status || 'checking...'}
          </span>
        </div>

        {/* Marquez Status */}
        <div className="flex items-center gap-2">
          {marquezLoading ? (
            <Clock className="h-3 w-3 text-muted-foreground animate-spin" />
          ) : marquezHealth?.status === 'healthy' ? (
            <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
          ) : (
            <AlertTriangle className="h-3 w-3 text-red-600 dark:text-red-400" />
          )}
          <span className="text-muted-foreground">Marquez:</span>
          <span className={cn(
            marquezHealth?.status === 'healthy'
              ? 'text-green-600 dark:text-green-400'
              : 'text-red-600 dark:text-red-400'
          )}>
            {marquezHealth?.status || 'checking...'}
          </span>
        </div>

        {/* Job Runner */}
        <div className="flex items-center gap-2">
          {recentJobFailures.length > 0 ? (
            <AlertTriangle className="h-3 w-3 text-red-600 dark:text-red-400" />
          ) : (
            <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
          )}
          <span className="text-muted-foreground">Job runner:</span>
          <span
            className={cn(
              recentJobFailures.length > 0
                ? 'text-red-600 dark:text-red-400 font-medium'
                : 'text-green-600 dark:text-green-400',
            )}
          >
            {recentJobFailures.length > 0
              ? `${recentJobFailures.length} failure${recentJobFailures.length > 1 ? 's' : ''} (30m)`
              : 'Healthy'}
          </span>
          {jobFailures.length > 0 && (
            <span className="text-muted-foreground/80">· {jobFailureSummary}</span>
          )}
        </div>

        {/* Failed Runs */}
        {recentFailedRuns > 0 && (
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3 w-3 text-yellow-600 dark:text-yellow-400" />
            <span className="text-yellow-600 dark:text-yellow-400 font-medium">
              {recentFailedRuns} failed run{recentFailedRuns > 1 ? 's' : ''} (30m)
            </span>
          </div>
        )}
      </div>

      {/* Right side - Last update */}
      <div className="flex items-center gap-4">
        <span className="text-muted-foreground">
          Telemetry: {lineageTelemetry?.incompleteFacets ?? 0} pending backfills · {lineageTelemetry?.failedToday ?? 0} failed today · {lineageTelemetry?.jobsToday ?? 0} jobs today · {recentJobFailures.length} job failure{recentJobFailures.length === 1 ? '' : 's'} (30m)
        </span>
        <div className="flex items-center gap-2">
          {hasIssues && (
            <Badge variant="outline" className="text-xs bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border-yellow-500/20">
              <Activity className="h-3 w-3 mr-1" />
              Action Required
            </Badge>
          )}
          <span className="text-muted-foreground">
            Last poll:{' '}
            {prefectHealth?.timestamp
              ? formatDistanceToNow(prefectHealth.timestamp, { addSuffix: true })
              : 'never'}
          </span>
        </div>
      </div>
    </div>
  )
}
