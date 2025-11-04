/**
 * Agent Activity Panel
 *
 * Side panel showing recent agent actions and tool calls with live updates.
 */

import { Fragment, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { Activity, Wrench, MessageSquare, CheckCircle, XCircle, CloudUpload } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody } from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { fetchActivityEvents } from '@/api/activity'
import type { ActivityEvent } from '@/types'
import { useFeedback } from '@/components/feedback/FeedbackProvider'

const REFRESH_INTERVAL = 15_000
const ACTIVITY_LIMIT = 50
const HIGHLIGHT_WINDOW_MS = 3_000

interface AgentActivityPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AgentActivityPanel({ open, onOpenChange }: AgentActivityPanelProps) {
  const { addFeedback } = useFeedback()
  const [activityEvents, setActivityEvents] = useState<ActivityEvent[]>([])
  const [sseStatus, setSseStatus] = useState<'idle' | 'connecting' | 'open' | 'error'>('idle')
  const [sseError, setSseError] = useState<string | null>(null)
  const sseErrorAnnouncedRef = useRef(false)

  const pollingEnabled = !open || sseStatus !== 'open'
  const transportLabel = sseStatus === 'open' ? 'Live (SSE)' : `Live (Polling ${REFRESH_INTERVAL / 1000}s)`

  const {
    data: events = [],
    isLoading,
    isError,
    error,
  } = useQuery<ActivityEvent[]>({
    queryKey: ['activity', { limit: ACTIVITY_LIMIT }],
    queryFn: () => fetchActivityEvents(ACTIVITY_LIMIT),
    refetchInterval: pollingEnabled ? REFRESH_INTERVAL : false,
  })

  useEffect(() => {
    if (events.length > 0) {
      setActivityEvents(prev => mergeActivityEvents(events, prev))
    } else if (!open && events.length === 0) {
      setActivityEvents(events)
    }
  }, [events, open])

  useEffect(() => {
    if (!open) {
      setSseStatus('idle')
      setSseError(null)
      sseErrorAnnouncedRef.current = false
      return
    }

    let closed = false
    setSseStatus('connecting')
    setSseError(null)

    const source = new EventSource(`/api/activity/events?limit=${ACTIVITY_LIMIT}`)

    source.onopen = () => {
      if (!closed) {
        setSseStatus('open')
        sseErrorAnnouncedRef.current = false
      }
    }

    const handleSnapshot = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as { events?: ActivityEvent[] }
        if (Array.isArray(payload?.events)) {
          setActivityEvents(prev => mergeActivityEvents(payload.events ?? [], prev))
        }
      } catch (parseError) {
        console.warn('Failed to parse activity snapshot', parseError)
      }
    }

    const handleActivity = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as { event?: ActivityEvent }
        if (payload?.event) {
          const nextEvent = payload.event
          setActivityEvents(prev => mergeActivityEvents([nextEvent], prev))
        }
      } catch (parseError) {
        console.warn('Failed to parse activity event', parseError)
      }
    }

    source.addEventListener('snapshot', handleSnapshot)
    source.addEventListener('activity', handleActivity)

    source.onerror = () => {
      if (closed) return
      setSseStatus('error')
      setSseError('Live updates unavailable; falling back to polling every 15 seconds.')
      if (!sseErrorAnnouncedRef.current) {
        addFeedback({
          variant: 'warning',
          title: 'Live activity stream degraded',
          description: 'Realtime updates are temporarily unavailable. Falling back to periodic refresh.',
        })
        sseErrorAnnouncedRef.current = true
      }
      source.close()
    }

    return () => {
      closed = true
      source.removeEventListener('snapshot', handleSnapshot)
      source.removeEventListener('activity', handleActivity)
      source.close()
    }
  }, [open, addFeedback])

  const highlightCutoff = Date.now() - HIGHLIGHT_WINDOW_MS
  const mappedEvents = activityEvents.map((event) => {
    const category = (event.category || event.type || 'general').toString().toLowerCase()
    const status = (event.status || '').toString().toLowerCase()
    const baseSuccess =
      typeof event.success === 'boolean'
        ? event.success
        : !['failed', 'errored', 'rejected', 'failed-to-start'].includes(status)

    const timestamp = new Date(event.timestamp)
    const timestampSAST = timestamp.toLocaleString('en-ZA', {
      timeZone: 'Africa/Johannesburg',
      hour12: false,
    })
    const isRecent = timestamp.getTime() >= highlightCutoff

    let icon = Activity
    if (category === 'hil') icon = CheckCircle
    else if (category === 'import') icon = CloudUpload
    else if (category === 'assistant' || category === 'chat') icon = MessageSquare
    else if (category === 'tool' || category === 'command') icon = Wrench

    let title = event.message
    if (!title) {
      if (category === 'hil' && event.runId) {
        title = `${event.status ?? 'Updated'} ${event.runId}`
      } else if (category === 'import' && event.label) {
        title = `${event.action ? `${event.action} – ` : ''}${event.label}`
      } else if (event.action) {
        title = `${event.action} ${event.runId ?? event.jobId ?? ''}`.trim()
      } else {
        title = category.charAt(0).toUpperCase() + category.slice(1)
      }
    }

    const detailParts: string[] = []
    if (event.operator) {
      detailParts.push(event.operator)
    }
    if (event.runId && category !== 'hil') {
      detailParts.push(event.runId)
    }
    if (event.jobId) {
      detailParts.push(event.jobId)
    }

    return {
      raw: event,
      icon,
      title,
      detailParts,
      success: baseSuccess,
      category,
      timestamp,
      isRecent,
      timestampSAST,
    }
  })

  const isInitialLoading = isLoading && activityEvents.length === 0 && sseStatus !== 'open'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader onClose={() => onOpenChange(false)}>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            <SheetTitle>Agent Activity</SheetTitle>
            <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-300">
              {transportLabel}
            </Badge>
          </div>
        </SheetHeader>
        <SheetBody>
          {(isError || sseError) && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
              {isError && (error instanceof Error ? error.message : 'Unable to load activity events.')}
              {sseError && (
                <div className="mt-1 text-xs text-red-600 dark:text-red-300">
                  {sseError}
                </div>
              )}
            </div>
          )}
          {isInitialLoading && (
            <div className="space-y-2 text-xs text-muted-foreground">
              Loading recent activity…
            </div>
          )}
          <div className="space-y-1" aria-live="polite" role="log">
            {mappedEvents.map(({ raw, icon: Icon, title, detailParts, success, category, timestamp, timestampSAST, isRecent }) => {
              return (
                <div
                  key={raw.id}
                  className={cn(
                    'border-l-2 border-muted pl-4 py-3 transition-colors rounded-r',
                    'hover:bg-accent/50',
                    isRecent && 'bg-primary/5 border-primary/60',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-3 flex-1">
                      <div
                        className={cn(
                          'p-1.5 rounded-lg',
                          success
                            ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                            : 'bg-red-500/10 text-red-600 dark:text-red-400'
                        )}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium break-words">
                            {title}
                          </span>
                          {success ? (
                            <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
                          ) : (
                            <XCircle className="h-3 w-3 text-red-600 dark:text-red-400" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline" className="text-xs capitalize">
                            {category.replace('_', ' ')}
                          </Badge>
                          {detailParts.map((part, index) => (
                            <Fragment key={`${raw.id}-detail-${index}`}>
                              <span>•</span>
                              <span>{part}</span>
                            </Fragment>
                          ))}
                        </div>
                        <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span>{formatDistanceToNow(timestamp, { addSuffix: true })}</span>
                          <span className="text-[11px] text-muted-foreground/80">SAST {timestampSAST}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {!isInitialLoading && mappedEvents.length === 0 && (
            <div className="flex items-center justify-center py-12 text-center">
              <div>
                <Activity className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No recent activity</p>
              </div>
            </div>
          )}
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}

function mergeActivityEvents(
  incoming: ActivityEvent[],
  existing: ActivityEvent[],
): ActivityEvent[] {
  if (!Array.isArray(incoming) || incoming.length === 0) {
    return existing
  }

  const map = new Map<string, ActivityEvent>()
  const combined = [...incoming, ...existing]

  for (const event of combined) {
    if (event && event.id && !map.has(event.id)) {
      map.set(event.id, event)
    }
  }

  return Array.from(map.values())
    .sort((a, b) => {
      const timeA = new Date(a.timestamp ?? 0).getTime()
      const timeB = new Date(b.timestamp ?? 0).getTime()
      return timeB - timeA
    })
    .slice(0, ACTIVITY_LIMIT)
}
