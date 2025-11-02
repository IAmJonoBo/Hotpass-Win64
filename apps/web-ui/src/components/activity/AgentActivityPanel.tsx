/**
 * Agent Activity Panel
 *
 * Side panel showing recent agent actions and tool calls.
 */

import { Fragment, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { Activity, Wrench, MessageSquare, CheckCircle, XCircle, CloudUpload } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody } from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { fetchActivityEvents } from '@/api/activity'
import type { ActivityEvent } from '@/types'

const REFRESH_INTERVAL = 15_000
const ACTIVITY_LIMIT = 50
const HIGHLIGHT_WINDOW_MS = 60_000

interface AgentActivityPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AgentActivityPanel({ open, onOpenChange }: AgentActivityPanelProps) {
  const {
    data: events = [],
    isLoading,
    isError,
    error,
  } = useQuery<ActivityEvent[]>({
    queryKey: ['activity', { limit: ACTIVITY_LIMIT }],
    queryFn: () => fetchActivityEvents(ACTIVITY_LIMIT),
    refetchInterval: REFRESH_INTERVAL,
  })

  const mappedEvents = useMemo(() => {
    const now = Date.now()
    return events.map((event) => {
      const category = (event.category || event.type || 'general').toString().toLowerCase()
      const status = (event.status || '').toString().toLowerCase()
      const baseSuccess =
        typeof event.success === 'boolean'
          ? event.success
          : !['failed', 'errored', 'rejected', 'failed-to-start'].includes(status)

      const timestamp = new Date(event.timestamp)
      const isRecent = now - timestamp.getTime() <= HIGHLIGHT_WINDOW_MS

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
      }
    })
  }, [events])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader onClose={() => onOpenChange(false)}>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            <SheetTitle>Agent Activity</SheetTitle>
          </div>
        </SheetHeader>
        <SheetBody>
          {isError && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
              {error instanceof Error ? error.message : 'Unable to load activity events.'}
            </div>
          )}
          {isLoading && (
            <div className="space-y-2 text-xs text-muted-foreground">
              Loading recent activity…
            </div>
          )}
          <div className="space-y-1">
            {mappedEvents.map(({ raw, icon: Icon, title, detailParts, success, category, timestamp, isRecent }) => {
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
                        <div className="text-xs text-muted-foreground">
                          {formatDistanceToNow(timestamp, { addSuffix: true })}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {!isLoading && mappedEvents.length === 0 && (
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
