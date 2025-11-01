/**
 * Approval Panel Component
 *
 * Slide-over panel for human-in-the-loop approval/rejection of pipeline runs.
 */

import { useMemo, useState } from 'react'
import { CheckCircle, XCircle, MessageSquare, Clock, User, AlertTriangle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetBody } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useApproveRun, useRejectRun, useGetRunApproval, useGetRunHistory } from '@/store/hilStore'
import type { PrefectFlowRun, QAResult } from '@/types'
import { useAuth } from '@/auth'

interface ApprovalPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  run: PrefectFlowRun
  qaResults: QAResult[]
  onOpenAssistant?: (message: string) => void
  canApprove: boolean
}

export function ApprovalPanel({
  open,
  onOpenChange,
  run,
  qaResults,
  onOpenAssistant,
  canApprove,
}: ApprovalPanelProps) {
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: currentApproval } = useGetRunApproval(run.id)
  const { data: history = [] } = useGetRunHistory(run.id)
  const approveRun = useApproveRun()
  const rejectRun = useRejectRun()

  const { user, storageReady, hasRole } = useAuth()

  const operator = useMemo(
    () => user?.email || user?.name || user?.id || 'unknown-operator',
    [user],
  )
  const approvalsEnabled = canApprove && storageReady && hasRole(['approver', 'admin'])
  const guardUnavailable = !storageReady

  const passedChecks = qaResults.filter(r => r.status === 'passed').length
  const totalChecks = qaResults.length
  const hasWarnings = qaResults.some(r => r.status === 'warning')
  const hasFailed = qaResults.some(r => r.status === 'failed')

  const handleError = (message: string, cause?: unknown) => {
    console.error(message, cause)
    setError(message)
  }

  const handleApprove = async () => {
    if (!approvalsEnabled) {
      handleError('You do not have permission to approve this run.')
      return
    }
    try {
      await approveRun.mutateAsync({
        runId: run.id,
        operator,
        comment: comment || undefined,
      })
      setComment('')
      setError(null)
      onOpenChange(false)
    } catch (err) {
      handleError('Failed to approve run. Secure storage may be unavailable.', err)
      throw err
    }
  }

  const handleReject = async () => {
    if (!approvalsEnabled) {
      handleError('You do not have permission to reject this run.')
      return
    }
    try {
      await rejectRun.mutateAsync({
        runId: run.id,
        operator,
        reason: reason || 'QA checks did not pass',
        comment: comment || undefined,
      })
      if (onOpenAssistant) {
        onOpenAssistant(
          `Explain why run ${run.id} (${run.name}) failed QA and propose remediation. QA results: ${JSON.stringify(qaResults, null, 2)}`,
        )
      }
      setComment('')
      setReason('')
      setError(null)
      onOpenChange(false)
    } catch (err) {
      handleError('Failed to reject run. Secure storage may be unavailable.', err)
      throw err
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader onClose={() => onOpenChange(false)}>
          <SheetTitle>Approval Required</SheetTitle>
        </SheetHeader>
        <SheetBody className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Run Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Run Name:</span>
                <span className="font-medium">{run.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <Badge variant="outline">{run.state_name}</Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Operator:</span>
                <span className="font-medium">{operator}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Started:</span>
                <span>
                  {run.start_time
                    ? formatDistanceToNow(new Date(run.start_time), { addSuffix: true })
                    : 'Not started'}
                </span>
              </div>
            </CardContent>
          </Card>

          {guardUnavailable && (
            <Card className="border-amber-500/40 bg-amber-500/10" role="alert" aria-live="assertive">
              <CardContent className="pt-4 text-sm text-amber-800 dark:text-amber-200">
                Secure storage is initialising. Approvals will be enabled once session keys are ready.
              </CardContent>
            </Card>
          )}

          {!approvalsEnabled && !guardUnavailable && (
            <Card className="border-destructive/40 bg-destructive/10" role="alert" aria-live="assertive">
              <CardContent className="pt-4 text-sm text-destructive">
                You do not have the approver role required to action this run.
              </CardContent>
            </Card>
          )}

          {error && (
            <Card className="border-destructive/40 bg-destructive/10" role="alert" aria-live="assertive">
              <CardContent className="pt-4 text-sm text-destructive">{error}</CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">QA Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Checks Passed</span>
                  <Badge
                    variant="outline"
                    className={cn(
                      passedChecks === totalChecks
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-yellow-600 dark:text-yellow-400',
                    )}
                  >
                    {passedChecks}/{totalChecks}
                  </Badge>
                </div>
                <div className="space-y-2">
                  {qaResults.map((result, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm">
                      {result.status === 'passed' && (
                        <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
                      )}
                      {result.status === 'failed' && (
                        <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                      )}
                      {result.status === 'warning' && (
                        <Clock className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                      )}
                      <span className="flex-1">{result.check}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {currentApproval && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Current Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status:</span>
                  <Badge
                    variant="outline"
                    className={cn(
                      currentApproval.status === 'approved'
                        ? 'text-green-600 dark:text-green-400'
                        : currentApproval.status === 'rejected'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-yellow-600 dark:text-yellow-400',
                    )}
                  >
                    {currentApproval.status}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Operator:</span>
                  <span className="font-medium">{currentApproval.operator}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">When:</span>
                  <span>{formatDistanceToNow(new Date(currentApproval.timestamp), { addSuffix: true })}</span>
                </div>
                {currentApproval.comment && (
                  <div>
                    <span className="text-muted-foreground">Comment:</span>
                    <p className="mt-1 text-sm bg-muted p-2 rounded">{currentApproval.comment}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {history.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">History</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {history.map(entry => (
                    <div key={entry.id} className="border-l-2 border-muted pl-3 py-1">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <User className="h-3 w-3" />
                        {entry.operator}
                        <Badge variant="outline" className="text-xs uppercase tracking-wide">
                          {entry.action}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
                      </div>
                      {entry.comment && (
                        <div className="text-xs mt-1 bg-muted/50 p-2 rounded">{entry.comment}</div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">Comment (optional)</label>
            <Input
              placeholder="Add a comment..."
              value={comment}
              onChange={event => setComment(event.target.value)}
              disabled={!approvalsEnabled}
            />
          </div>

          {hasFailed && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Rejection Reason</label>
              <Input
                placeholder="Why are you rejecting this run?"
                value={reason}
                onChange={event => setReason(event.target.value)}
                disabled={!approvalsEnabled}
              />
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Button className="w-full" onClick={handleApprove} disabled={!approvalsEnabled || approveRun.isPending}>
              <CheckCircle className="mr-2 h-4 w-4" />
              Approve and Continue Downstream Tasks
            </Button>
            <Button
              variant="destructive"
              className="w-full"
              onClick={handleReject}
              disabled={!approvalsEnabled || rejectRun.isPending}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Reject and Open Chat with Agent
            </Button>
            {onOpenAssistant && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  onOpenAssistant(`Help me understand the QA results for run ${run.id} (${run.name})`)
                  onOpenChange(false)
                }}
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                Ask Assistant About This Run
              </Button>
            )}
          </div>

          {hasWarnings && !hasFailed && (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 text-sm">
              <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 font-medium">
                <AlertTriangle className="h-4 w-4" />
                Warnings Detected
              </div>
              <p className="text-muted-foreground mt-1 text-xs">
                This run has {qaResults.filter(r => r.status === 'warning').length} warning(s). Review carefully before approving.
              </p>
            </div>
          )}
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}
