import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { MessageSquare, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react'
import * as React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { clampText } from '@/lib/security'
import { prefectApi, mockPrefectData } from '@/api/prefect'
import type { PrefectFlowRun } from '@/types'

interface RefineRunRow {
  id: string
  name: string
  profile?: string
  status: 'completed' | 'pending' | 'running' | 'error'
  startedAt?: string
  finishedAt?: string
  parameters?: Record<string, unknown>
  notes?: string
  dataDocs?: string
}

const MAX_FEEDBACK_LENGTH = 500
const REFRESH_INTERVAL = 15_000
const HIGHLIGHT_WINDOW_MS = 60_000
const MAX_ROWS = 15

const deriveStatus = (run: PrefectFlowRun): RefineRunRow['status'] => {
  const state = (run.state_type ?? '').toLowerCase()
  switch (state) {
    case 'completed':
      return 'completed'
    case 'running':
      return 'running'
    case 'failed':
    case 'crashed':
    case 'cancelled':
      return 'error'
    default:
      return 'pending'
  }
}

const formatNotes = (parameters: Record<string, unknown>): string | undefined => {
  if (typeof parameters.notes === 'string') {
    return parameters.notes
  }
  if (typeof parameters.comment === 'string') {
    return parameters.comment
  }
  return undefined
}

export function LiveRefinementPanel() {
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string | undefined>>({})
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [telemetryError, setTelemetryError] = useState<string | null>(null)
  const [lastSync, setLastSync] = useState<Date | null>(null)

  const recentMapRef = useRef<Record<string, number>>({})

  const {
    data: flowRuns = mockPrefectData.flowRuns,
    refetch,
    isFetching,
    isError,
    error,
  } = useQuery({
    queryKey: ['prefect', 'refine-runs'],
    queryFn: async () => {
      try {
        return await prefectApi.getFlowRuns({ limit: 25 })
      } catch (apiError) {
        console.warn('Failed to load Prefect runs, falling back to mock data', apiError)
        return mockPrefectData.flowRuns
      }
    },
    refetchInterval: REFRESH_INTERVAL,
  })

  const rows: RefineRunRow[] = useMemo(() => {
    return flowRuns
      .filter(run => {
        const name = (run.name ?? '').toLowerCase()
        return name.includes('refine') || name.includes('run') || !run.flow_id
      })
      .slice(0, MAX_ROWS)
      .map((run) => {
        const status = deriveStatus(run)
        const parameters = (run.parameters ?? {}) as Record<string, unknown>
        const profile = typeof parameters.profile === 'string' ? parameters.profile : undefined
        const notes = formatNotes(parameters)
        const docsUrl = typeof parameters.data_docs_url === 'string' ? parameters.data_docs_url : undefined

        return {
          id: run.id,
          name: run.name ?? run.id,
          profile,
          status,
          startedAt: run.start_time ?? run.created,
          finishedAt: run.end_time ?? run.updated,
          parameters,
          notes,
          dataDocs: docsUrl,
        }
      })
  }, [flowRuns])

  useEffect(() => {
    const now = Date.now()
    const nextHighlightMap = { ...recentMapRef.current }
    rows.forEach(row => {
      if (!(row.id in nextHighlightMap)) {
        nextHighlightMap[row.id] = now
      }
    })
    Object.entries(nextHighlightMap).forEach(([id, timestamp]) => {
      if (now - timestamp > HIGHLIGHT_WINDOW_MS) {
        delete nextHighlightMap[id]
      }
    })
    recentMapRef.current = nextHighlightMap
    setLastSync(new Date())
  }, [rows])

  useEffect(() => {
    let cancelled = false
    async function fetchCsrf() {
      try {
        const response = await fetch('/telemetry/operator-feedback/csrf', {
          method: 'GET',
          credentials: 'include',
          headers: { Accept: 'application/json' },
        })
        if (!response.ok) {
          throw new Error(`Failed to initialise CSRF token: ${response.status}`)
        }
        const payload = (await response.json()) as { token?: string }
        if (!cancelled) {
          setCsrfToken(payload.token ?? null)
          setTelemetryError(null)
        }
      } catch (fetchError) {
        console.error('Unable to fetch telemetry CSRF token', fetchError)
        if (!cancelled) {
          setTelemetryError('Feedback temporarily unavailable while security context initialises.')
          setCsrfToken(null)
        }
      }
    }

    fetchCsrf()
    return () => {
      cancelled = true
    }
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
        body: JSON.stringify({ rowId: runId, feedback: sanitised, metadata: { submittedAt: new Date().toISOString() } }),
      })
      if (!response.ok) {
        throw new Error(`Feedback submission failed: ${response.status}`)
      }
      setTelemetryError(null)
    } catch (submitError) {
      console.error('Failed to submit telemetry feedback', submitError)
      setTelemetryError('Could not submit feedback. Please retry once the session stabilises.')
    }

    setFeedback(prev => ({ ...prev, [runId]: '' }))
    setFeedbackErrors(prev => ({ ...prev, [runId]: undefined }))
    setExpandedRow(null)
  }

  const getStatusIcon = (status: RefineRunRow['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
      case 'running':
        return <RefreshCw className="h-4 w-4 text-primary animate-spin" />
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
      default:
        return <RefreshCw className="h-4 w-4 text-blue-600 dark:text-blue-400" />
    }
  }

  const completedCount = rows.filter(r => r.status === 'completed').length
  const runningCount = rows.filter(r => r.status === 'running').length
  const pendingCount = rows.filter(r => r.status === 'pending').length
  const errorCount = rows.filter(r => r.status === 'error').length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Live Refinement</CardTitle>
            <CardDescription>
              Prefect refinement runs with real-time updates
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {lastSync && (
              <span>
                Last sync {formatDistanceToNow(lastSync, { addSuffix: true })}
              </span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {telemetryError && (
          <div className="mb-3 rounded border border-red-500/40 bg-red-500/10 p-2 text-sm text-red-700 dark:text-red-300" role="alert">
            {telemetryError}
          </div>
        )}
        {isError && (
          <div className="mb-3 rounded border border-yellow-500/40 bg-yellow-500/10 p-2 text-sm text-yellow-700 dark:text-yellow-400" role="alert">
            {error instanceof Error ? error.message : 'Failed to refresh Prefect runs. Displaying cached data.'}
          </div>
        )}
        <div className="flex gap-4 mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium">{completedCount} completed</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">{runningCount} running</span>
          </div>
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium">{pendingCount} pending</span>
          </div>
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <span className="text-sm font-medium">{errorCount} errors</span>
          </div>
        </div>

        <div className="rounded-lg border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Timing</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => {
                const highlight = recentMapRef.current[row.id] !== undefined
                const startedAgo = row.startedAt ? formatDistanceToNow(new Date(row.startedAt), { addSuffix: true }) : '—'
                const finishedAgo = row.finishedAt ? formatDistanceToNow(new Date(row.finishedAt), { addSuffix: true }) : '—'
                return (
                  <React.Fragment key={row.id}>
                    <TableRow className={cn(highlight && 'bg-primary/5')}>
                      <TableCell className="font-medium text-sm">
                        <div className="flex flex-col">
                          <span className="truncate">{row.name}</span>
                          {row.profile && (
                            <span className="text-xs uppercase text-muted-foreground">Profile {row.profile}</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <span>Started {startedAgo}</span>
                        {row.status === 'completed' && (
                          <span className="block">Completed {finishedAgo}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(row.status)}
                          <Badge
                            variant="outline"
                            className={cn(
                              row.status === 'completed'
                                ? 'text-green-600 dark:text-green-400'
                                : row.status === 'pending'
                                ? 'text-blue-600 dark:text-blue-400'
                                : row.status === 'running'
                                  ? 'text-primary'
                                  : 'text-red-600 dark:text-red-400'
                            )}
                          >
                            {row.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {row.notes ?? '—'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {row.dataDocs && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => window.open(row.dataDocs, '_blank', 'noreferrer')}
                            >
                              Docs
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpandedRow(prev => (prev === row.id ? null : row.id))}
                          >
                            <MessageSquare className="h-4 w-4" />
                            <span className="sr-only">Toggle feedback</span>
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                    {expandedRow === row.id && (
                      <TableRow className="bg-muted/40">
                        <TableCell colSpan={5}>
                          <div className="px-4 py-3 space-y-3">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-semibold">Operator feedback</h4>
                              <span className="text-xs text-muted-foreground">Max {MAX_FEEDBACK_LENGTH} characters</span>
                            </div>
                            <Input
                              value={feedback[row.id] ?? ''}
                              onChange={(event) => {
                                const raw = event.target.value
                                const sanitised = clampText(raw, MAX_FEEDBACK_LENGTH)
                                setFeedback(prev => ({ ...prev, [row.id]: sanitised }))
                                setFeedbackErrors(prev => ({ ...prev, [row.id]: undefined }))
                              }}
                              placeholder="Share context for operators reviewing this run"
                            />
                            {feedbackErrors[row.id] && (
                              <p className="text-xs text-red-600 dark:text-red-400">{feedbackErrors[row.id]}</p>
                            )}
                            <div className="mt-3 flex justify-end gap-2">
                              <Button variant="outline" size="sm" onClick={() => setExpandedRow(null)}>
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                className="gap-2"
                                onClick={() => handleFeedbackSubmit(row.id)}
                                disabled={!feedback[row.id]}
                              >
                                Submit
                              </Button>
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
