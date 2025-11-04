/**
 * Power Tools Launcher
 *
 * Quick access panel for common operations and CLI commands.
 */

import type { ElementType } from 'react'
import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Wrench,
  Terminal,
  Play,
  GitBranch,
  MessageSquare,
  Copy,
  CheckCircle,
  Loader2,
  XCircle,
  Clock,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { CommandJob } from '@/types'
import { runCommandJob, buildCommandJobLinks } from '@/api/commands'

interface PowerTool {
  id: string
  title: string
  description: string
  displayCommand: string
  commandParts?: string[]
  icon: ElementType
  action?: () => void
  disabled?: boolean
  disabledReason?: string
}

interface PowerToolsProps {
  onOpenAssistant?: () => void
}

interface CommandJobView {
  job: CommandJob
  logs: string[]
  status: CommandJob['status']
  error?: string | null
  toolId: string
  startedAt?: string | null
  completedAt?: string | null
}

export function PowerTools({ onOpenAssistant }: PowerToolsProps) {
  const navigate = useNavigate()
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null)
  const [runningToolId, setRunningToolId] = useState<string | null>(null)
  const [commandError, setCommandError] = useState<string | null>(null)
  const [jobs, setJobs] = useState<Record<string, CommandJobView>>({})
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const jobStreamsRef = useRef<Record<string, EventSource>>({})

  const environment =
    import.meta.env.HOTPASS_ENVIRONMENT ||
    import.meta.env.VITE_ENVIRONMENT ||
    'local'
  const isDocker = environment === 'docker'
  const MAX_JOB_LOG_LINES = 200

  useEffect(
    () => () => {
      Object.values(jobStreamsRef.current).forEach((source) => {
        try {
          source.close()
        } catch {
          // ignore
        }
      })
      jobStreamsRef.current = {}
    },
    [],
  )

  const copyCommand = useCallback((command: string, id: string) => {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return
    }
    navigator.clipboard
      .writeText(command)
      .then(() => {
        setCopiedCommand(id)
        setTimeout(() => setCopiedCommand(null), 2000)
      })
      .catch(() => {})
  }, [])

  const appendLog = useCallback(
    (logs: string[], entry: string) => {
      const next = [...logs, entry]
      if (next.length > MAX_JOB_LOG_LINES) {
        next.splice(0, next.length - MAX_JOB_LOG_LINES)
      }
      return next
    },
    [MAX_JOB_LOG_LINES],
  )

  const attachToJob = useCallback(
    (job: CommandJob, toolId: string) => {
      const { logUrl } = buildCommandJobLinks(job.id)
      const source = new EventSource(logUrl)
      jobStreamsRef.current[job.id] = source

      const parseEvent = (event: MessageEvent<string>) => {
        try {
          return JSON.parse(event.data) as Record<string, unknown>
        } catch (error) {
          console.warn('[powertools] failed to parse job event', error)
          return null
        }
      }

      source.addEventListener('snapshot', (event) => {
        const payload = parseEvent(event as MessageEvent<string>)
        if (!payload || !payload.job) return
        const jobPayload = payload.job as CommandJob & {
          log?: Array<{ message?: string; type?: string }>
        }
        const initialLogs = Array.isArray((payload.job as Record<string, unknown>).log)
          ? (jobPayload.log ?? [])
              .map((entry) =>
                entry?.message
                  ? `[${entry.type === 'stderr' ? 'stderr' : 'stdout'}] ${entry.message}`
                  : null,
              )
              .filter(Boolean) as string[]
          : undefined

        setJobs((prev) => {
          const previous = prev[job.id] ?? {
            job,
            logs: [],
            status: job.status ?? 'queued',
            error: null,
            toolId,
            startedAt: job.startedAt ?? job.createdAt ?? null,
            completedAt: job.completedAt ?? null,
          }
          return {
            ...prev,
            [job.id]: {
              ...previous,
              job: { ...previous.job, ...jobPayload },
              status: jobPayload.status ?? previous.status,
              logs: initialLogs ?? previous.logs,
              startedAt:
                jobPayload.startedAt ??
                previous.startedAt ??
                previous.job.startedAt ??
                previous.job.createdAt ??
                null,
              completedAt: jobPayload.completedAt ?? previous.completedAt ?? null,
              error: previous.error,
            },
          }
        })
      })

      source.addEventListener('metadata', (event) => {
        const payload = parseEvent(event as MessageEvent<string>)
        if (!payload || typeof payload.metadata !== 'object') return
        setJobs((prev) => {
          const previous = prev[job.id]
          if (!previous) return prev
          return {
            ...prev,
            [job.id]: {
              ...previous,
              job: {
                ...previous.job,
                metadata: payload.metadata as Record<string, unknown>,
              },
            },
          }
        })
      })

      source.addEventListener('log', (event) => {
        const payload = parseEvent(event as MessageEvent<string>)
        if (!payload || typeof payload.message !== 'string') return
        const stream = typeof payload.stream === 'string' ? payload.stream : 'stdout'
        const formatted = `[${stream}] ${payload.message.trimEnd()}`
        setJobs((prev) => {
          const previous = prev[job.id]
          if (!previous) return prev
          return {
            ...prev,
            [job.id]: {
              ...previous,
              logs: appendLog(previous.logs, formatted),
            },
          }
        })
      })

      source.addEventListener('error', () => {
        setJobs((prev) => {
          const previous = prev[job.id]
          if (!previous) return prev
          return {
            ...prev,
            [job.id]: {
              ...previous,
              error: 'Live updates unavailable. Attempting to recover…',
            },
          }
        })
      })

      source.addEventListener('finished', (event) => {
        const payload = parseEvent(event as MessageEvent<string>)
        const status =
          typeof payload?.status === 'string'
            ? (payload.status as CommandJob['status'])
            : 'succeeded'
        const exitCode = typeof payload?.exitCode === 'number' ? payload.exitCode : null
        const completedAt =
          typeof payload?.completedAt === 'string' ? payload.completedAt : new Date().toISOString()
        setJobs((prev) => {
          const previous = prev[job.id]
          if (!previous) return prev
          return {
            ...prev,
            [job.id]: {
              ...previous,
              job: {
                ...previous.job,
                status,
                exitCode,
                completedAt,
              },
              status,
              completedAt,
              error:
                status === 'failed'
                  ? (typeof payload?.error === 'string' ? payload.error : previous.error)
                  : previous.error,
            },
          }
        })
        source.close()
        delete jobStreamsRef.current[job.id]
      })
    },
    [appendLog],
  )

  const handleCommandTool = useCallback(
    async (tool: PowerTool) => {
      if (!tool.commandParts || tool.commandParts.length === 0) return
      setRunningToolId(tool.id)
      setCommandError(null)
      try {
        const job = await runCommandJob({
          command: tool.commandParts,
          label: tool.title,
        })
        setJobs((prev) => ({
          ...prev,
          [job.id]: {
            job,
            logs: [],
            status: job.status ?? 'queued',
            error: null,
            toolId: tool.id,
            startedAt: job.startedAt ?? job.createdAt ?? null,
            completedAt: job.completedAt ?? null,
          },
        }))
        setSelectedJobId(job.id)
        attachToJob(job, tool.id)
      } catch (error) {
        setCommandError(error instanceof Error ? error.message : 'Failed to start command')
      } finally {
        setRunningToolId(null)
      }
    },
    [attachToJob],
  )

  const handleToolPress = useCallback(
    (tool: PowerTool) => {
      if (tool.disabled) return
      if (tool.commandParts && tool.commandParts.length > 0) {
        void handleCommandTool(tool)
      } else if (tool.action) {
        tool.action()
      }
    },
    [handleCommandTool],
  )

  const handleOpenAssistant = useCallback(() => {
    if (onOpenAssistant) {
      onOpenAssistant()
    } else {
      navigate('/assistant')
    }
  }, [onOpenAssistant, navigate])

  const handleOpenLineage = useCallback(() => {
    navigate('/lineage')
  }, [navigate])

  const tools: PowerTool[] = useMemo(
    () => [
      {
        id: 'marquez',
        title: 'Start Marquez',
        description: 'Launch Marquez locally for lineage tracking',
        displayCommand: 'make marquez-up',
        commandParts: ['make', 'marquez-up'],
        icon: GitBranch,
        disabled: isDocker,
        disabledReason: 'Already running in Docker',
      },
      {
        id: 'demo-pipeline',
        title: 'Run Demo Pipeline',
        description: 'Execute a sample refinement pipeline',
        displayCommand: 'uv run hotpass refine --input-dir ./data --output-path ./dist/refined.xlsx',
        commandParts: [
          'uv',
          'run',
          'hotpass',
          'refine',
          '--input-dir',
          './data',
          '--output-path',
          './dist/refined.xlsx',
        ],
        icon: Play,
      },
      {
        id: 'lineage',
        title: 'Open Lineage',
        description: 'Navigate to the lineage visualization page',
        displayCommand: 'Navigate to /lineage',
        icon: GitBranch,
        action: handleOpenLineage,
      },
      {
        id: 'assistant',
        title: 'Open Assistant',
        description: 'Launch the AI assistant chat console',
        displayCommand: 'Navigate to /assistant',
        icon: MessageSquare,
        action: handleOpenAssistant,
      },
    ],
    [handleOpenAssistant, handleOpenLineage, isDocker],
  )

  const parseTimestamp = (value?: string | null) => {
    if (!value) return 0
    const parsed = Date.parse(value)
    return Number.isNaN(parsed) ? 0 : parsed
  }

  const jobList = useMemo(() => {
    const list = Object.values(jobs)
    return list.sort((a, b) => {
      const aTime = Math.max(
        parseTimestamp(a.job.updatedAt ?? null),
        parseTimestamp(a.completedAt),
        parseTimestamp(a.startedAt),
        parseTimestamp(a.job.createdAt ?? null),
      )
      const bTime = Math.max(
        parseTimestamp(b.job.updatedAt ?? null),
        parseTimestamp(b.completedAt),
        parseTimestamp(b.startedAt),
        parseTimestamp(b.job.createdAt ?? null),
      )
      return bTime - aTime
    })
  }, [jobs])

  const renderStatusBadge = (status: CommandJob['status']) => {
    const mapping: Record<CommandJob['status'], { className: string; icon: ElementType; spin?: boolean }> = {
      queued: {
        className: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-300',
        icon: Clock,
      },
      running: {
        className: 'bg-blue-500/10 text-blue-600 dark:text-blue-300',
        icon: Loader2,
        spin: true,
      },
      succeeded: {
        className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300',
        icon: CheckCircle,
      },
      failed: {
        className: 'bg-rose-500/10 text-rose-600 dark:text-rose-300',
        icon: XCircle,
      },
    }
    const variant = mapping[status]
    const Icon = variant.icon
    return (
      <Badge variant="outline" className={cn('flex items-center gap-1 text-xs', variant.className)}>
        <Icon className={cn('h-3 w-3', variant.spin ? 'animate-spin' : '')} />
        {status}
      </Badge>
    )
  }

  const formatRelative = (value?: string | null) => {
    if (!value) return '—'
    const parsed = Date.parse(value)
    if (Number.isNaN(parsed)) return '—'
    return formatDistanceToNow(parsed, { addSuffix: true })
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Wrench className="h-5 w-5 text-primary" />
          <CardTitle>Power Tools</CardTitle>
        </div>
        <CardDescription>
          Quick actions for common operations
          {isDocker && (
            <Badge variant="outline" className="ml-2 text-xs">
              Docker Mode
            </Badge>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tools.map((tool) => {
            const Icon = tool.icon
            const isCopied = copiedCommand === tool.id

            return (
              <div
                key={tool.id}
                className={cn(
                  'border rounded-lg p-4 space-y-3 transition-colors',
                  tool.disabled
                    ? 'bg-muted/50 border-muted'
                    : 'hover:border-primary hover:bg-accent/50'
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'p-2 rounded-lg',
                        tool.disabled
                          ? 'bg-muted'
                          : 'bg-primary/10 text-primary'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <h3 className="font-medium text-sm">{tool.title}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {tool.description}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Command Display */}
                <div className="relative">
                  <pre
                    className={cn(
                      'bg-muted rounded-md p-2 pr-8 text-xs font-mono flex items-center gap-2 overflow-x-auto',
                      tool.disabled && 'opacity-50'
                    )}
                    tabIndex={0}
                    role="region"
                    aria-label={`Command: ${tool.displayCommand}`}
                  >
                    <Terminal className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
                    <code className="flex-1 whitespace-nowrap">{tool.displayCommand}</code>
                  </pre>
                  {!tool.disabled && tool.commandParts && (
                    <button
                      onClick={() => copyCommand(tool.displayCommand, tool.id)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-background rounded"
                      title="Copy command"
                    >
                      {isCopied ? (
                        <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
                      ) : (
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      )}
                    </button>
                  )}
                </div>

                {/* Action Button */}
                <Button
                  size="sm"
                  className="w-full"
                  onClick={() => handleToolPress(tool)}
                  disabled={tool.disabled || (tool.commandParts && runningToolId === tool.id)}
                  variant={tool.disabled ? 'outline' : 'default'}
                >
                  {tool.disabled ? (
                    <>
                      <span className="mr-2">⊘</span>
                      {tool.disabledReason}
                    </>
                  ) : tool.commandParts ? (
                    runningToolId === tool.id ? (
                      <>
                        <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                        Running…
                      </>
                    ) : (
                      <>
                        <Terminal className="mr-2 h-3 w-3" />
                        Run Command
                      </>
                    )
                  ) : (
                    <>
                      Go to {tool.title}
                    </>
                  )}
                </Button>
              </div>
            )
          })}
        </div>

        {commandError && (
          <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {commandError}
          </div>
        )}

        {jobList.length > 0 && (
          <div className="mt-6 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Recent command runs</h3>
              <Badge variant="outline" className="text-xs">
                {jobList.filter((job) => job.status === 'running').length} running
              </Badge>
            </div>
            {jobList.map((job) => (
              <div
                key={job.job.id}
                className={cn(
                  'cursor-pointer rounded-xl border border-border/60 bg-background/95 p-4 transition hover:border-primary/50',
                  selectedJobId === job.job.id && 'border-primary/60 shadow-sm',
                )}
                onClick={() => setSelectedJobId(job.job.id)}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {job.job.label ?? job.job.command?.join(' ') ?? job.job.id}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Started {formatRelative(job.startedAt ?? job.job.createdAt ?? null)}
                    </p>
                  </div>
                  {renderStatusBadge(job.status)}
                </div>
                {job.error && (
                  <div className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-300">
                    {job.error}
                  </div>
                )}
                <div
                  className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-border/40 bg-muted/20 p-3 font-mono text-[11px] leading-relaxed text-foreground"
                  aria-live="polite"
                  role="log"
                >
                  {job.logs.length === 0 ? (
                    <p className="text-muted-foreground">Waiting for logs…</p>
                  ) : (
                    job.logs.map((line, index) => (
                      <div key={`${job.job.id}-log-${index}`} className="whitespace-pre-wrap">
                        {line}
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-2 flex flex-wrap items-center justify-between text-[11px] text-muted-foreground">
                  <span>Job ID {job.job.id}</span>
                  {typeof job.job.exitCode === 'number' && (
                    <span>Exit code {job.job.exitCode}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Docker Notice */}
        {isDocker && (
          <div className="mt-4 bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-sm">
            <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400 font-medium mb-1">
              <Terminal className="h-4 w-4" />
              Running in Docker
            </div>
            <p className="text-xs text-muted-foreground">
              Some commands are unavailable or modified when running in containerized mode.
              Marquez and Prefect are already running as services.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
