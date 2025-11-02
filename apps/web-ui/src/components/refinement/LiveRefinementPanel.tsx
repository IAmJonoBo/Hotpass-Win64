/**
 * Live Refinement Panel
 *
 * Shows recently refined rows with real-time updates and operator feedback capability.
 */

import { useState, useEffect } from 'react'
import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, RefreshCw, CheckCircle, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { clampText } from '@/lib/security'
import { formatDistanceToNow } from 'date-fns'

interface RefinedRow {
  id: string
  source: string
  entity: string
  status: 'completed' | 'pending' | 'error'
  refined_at: string
  notes?: string
  operatorFeedback?: string
}

// Mock data generator
const MAX_FEEDBACK_LENGTH = 500

function generateMockRows(): RefinedRow[] {
  const sources = ['aviation.xlsx', 'maritime.csv', 'logistics.json', 'freight.xlsx']
  const entities = ['Airlines', 'Airports', 'Routes', 'Vessels', 'Ports', 'Shipments', 'Warehouses']
  const statuses: Array<'completed' | 'pending' | 'error'> = ['completed', 'completed', 'completed', 'pending', 'error']

  return Array.from({ length: 15 }, (_, i) => ({
    id: `row-${i + 1}`,
    source: sources[Math.floor(Math.random() * sources.length)],
    entity: entities[Math.floor(Math.random() * entities.length)],
    status: statuses[Math.floor(Math.random() * statuses.length)],
    refined_at: new Date(Date.now() - Math.random() * 3600000).toISOString(),
    notes: Math.random() > 0.7 ? 'Duplicate detected, merged' : undefined,
  }))
}

export function LiveRefinementPanel() {
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string | undefined>>({})
  const [lastSync, setLastSync] = useState(new Date())
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [telemetryError, setTelemetryError] = useState<string | null>(null)

  // Fetch refined rows with auto-refresh
  const { data: rows = [], refetch } = useQuery({
    queryKey: ['refined-rows'],
    queryFn: async () => {
      // In production, this would fetch from the API
      await new Promise(resolve => setTimeout(resolve, 500))
      return generateMockRows()
    },
    refetchInterval: 15000, // Refresh every 15 seconds
  })

  // Update last sync time on refetch
  useEffect(() => {
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
      } catch (error) {
        console.error('Unable to fetch telemetry CSRF token', error)
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

  const handleFeedbackSubmit = async (rowId: string) => {
    const rawFeedback = feedback[rowId]
    const sanitised = clampText(rawFeedback || '', MAX_FEEDBACK_LENGTH).trim()
    if (!sanitised || !csrfToken || feedbackErrors[rowId]) return

    try {
      const response = await fetch('/telemetry/operator-feedback', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
        body: JSON.stringify({ rowId, feedback: sanitised, metadata: { submittedAt: new Date().toISOString() } }),
      })
      if (!response.ok) {
        throw new Error(`Feedback submission failed: ${response.status}`)
      }
      setTelemetryError(null)
    } catch (error) {
      console.error('Failed to submit telemetry feedback', error)
      setTelemetryError('Could not submit feedback. Please retry once the session stabilises.')
    }

    // Clear feedback and collapse
    setFeedback(prev => ({ ...prev, [rowId]: '' }))
    setFeedbackErrors(prev => ({ ...prev, [rowId]: undefined }))
    setExpandedRow(null)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
      case 'pending':
        return <RefreshCw className="h-4 w-4 text-blue-600 dark:text-blue-400 animate-spin" />
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
      default:
        return null
    }
  }

  const completedCount = rows.filter(r => r.status === 'completed').length
  const pendingCount = rows.filter(r => r.status === 'pending').length
  const errorCount = rows.filter(r => r.status === 'error').length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Live Refinement</CardTitle>
            <CardDescription>
              Recent row-level refinements with real-time updates
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
        <CardContent>
          {telemetryError && (
            <div className="mb-3 rounded border border-red-500/40 bg-red-500/10 p-2 text-sm text-red-700 dark:text-red-300" role="alert">
              {telemetryError}
            </div>
          )}
          {/* Summary Stats */}
          <div className="flex gap-4 mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
            <span className="text-sm font-medium">{completedCount} completed</span>
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

        {/* Refinement Table */}
        <div className="rounded-lg border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Refined At</TableHead>
                <TableHead>Notes</TableHead>
                <TableHead className="text-right">Feedback</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.slice(0, 10).map((row) => (
                <React.Fragment key={row.id}>
                  <TableRow key={row.id}>
                    <TableCell className="font-medium text-sm">{row.source}</TableCell>
                    <TableCell className="text-sm">{row.entity}</TableCell>
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
                              : 'text-red-600 dark:text-red-400'
                          )}
                        >
                          {row.status}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(row.refined_at), { addSuffix: true })}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {row.notes || '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setExpandedRow(expandedRow === row.id ? null : row.id)
                        }
                        disabled={!csrfToken}
                      >
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                  {expandedRow === row.id && (
                    <TableRow>
                      <TableCell colSpan={6} className="bg-muted/50">
                        <div className="p-3 space-y-2">
                          <label className="text-sm font-medium">
                            Operator feedback on row {row.id}:
                          </label>
                          <div className="flex gap-2 items-start">
                            <div className="flex-1 space-y-1">
                              <Input
                                placeholder="Add your feedback..."
                                value={feedback[row.id] || ''}
                                onChange={(e) => {
                                  const nextValue = clampText(e.target.value, MAX_FEEDBACK_LENGTH)
                                  setFeedback(prev => ({
                                    ...prev,
                                    [row.id]: nextValue,
                                  }))
                                  setFeedbackErrors(prev => ({
                                    ...prev,
                                    [row.id]: nextValue.trim().length === 0
                                      ? 'Feedback cannot be empty.'
                                      : undefined,
                                  }))
                                }}
                                onKeyPress={(e) => {
                                  if (e.key === 'Enter') {
                                    handleFeedbackSubmit(row.id)
                                  }
                                }}
                                maxLength={MAX_FEEDBACK_LENGTH}
                              />
                              {feedbackErrors[row.id] && (
                                <p className="text-xs text-red-600 dark:text-red-400" role="alert">
                                  {feedbackErrors[row.id]}
                                </p>
                              )}
                            </div>
                            <Button
                              size="sm"
                              onClick={() => handleFeedbackSubmit(row.id)}
                              disabled={!feedback[row.id]?.trim() || Boolean(feedbackErrors[row.id])}
                            >
                              Submit
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setExpandedRow(null)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Telemetry Caption */}
        <div className="mt-4 text-xs text-muted-foreground flex items-center justify-between bg-muted/30 rounded-lg p-3">
          <div className="flex gap-4">
            <span>
              <strong>Telemetry:</strong> {pendingCount} pending backfills
            </span>
            <span>•</span>
            <span>
              last sync {formatDistanceToNow(lastSync, { addSuffix: true })}
            </span>
            <span>•</span>
            <span>source: Marquez namespace=hotpass</span>
          </div>
          <Badge variant="outline" className="text-xs">
            Live
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}
