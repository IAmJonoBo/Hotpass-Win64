import { useCallback, useMemo, useRef, useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import {
  Activity,
  ArrowRightCircle,
  CheckCircle2,
  CloudUpload,
  FileSpreadsheet,
  Files,
  Loader2,
  ShieldAlert,
  Users,
  XCircle,
} from 'lucide-react'
import type { PrefectFlowRun, HILApproval } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn, formatBytes, formatDuration, getStatusColor } from '@/lib/utils'

interface DatasetImportPanelProps {
  flowRuns: PrefectFlowRun[]
  hilApprovals: Record<string, HILApproval>
  isLoadingRuns: boolean
  onOpenAssistant?: (message?: string) => void
}

interface PendingUpload {
  id: string
  fileName: string
  size: number
  profile: string
  hasNotes: boolean
  status: 'queued' | 'validating' | 'ready'
  addedAt: number
}

const PROFILE_OPTIONS = [
  { value: 'generic', label: 'Generic' },
  { value: 'aviation', label: 'Aviation' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'enrichment', label: 'Enrichment + network' },
]

export function DatasetImportPanel({ flowRuns, hilApprovals, isLoadingRuns, onOpenAssistant }: DatasetImportPanelProps) {
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
  const [activeProfile, setActiveProfile] = useState(PROFILE_OPTIONS[0].value)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return

    const maxFileSize = 1_000_000_000 // 1GB
    const acceptedTypes = ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/zip']

    const additions: PendingUpload[] = []

    Array.from(fileList).forEach(file => {
      if (file.size > maxFileSize) {
        setError(`"${file.name}" exceeds the 1GB limit. Split the dataset or compress it before retrying.`)
        return
      }

      if (!acceptedTypes.includes(file.type) && !file.name.endsWith('.csv') && !file.name.endsWith('.xlsx') && !file.name.endsWith('.zip')) {
        setError(`"${file.name}" is not a supported format. Upload CSV, XLSX, or ZIP bundles.`)
        return
      }

      additions.push({
        id: `${Date.now()}-${file.name}`,
        fileName: file.name,
        size: file.size,
        profile: activeProfile,
        hasNotes: notes.trim().length > 0,
        status: 'queued',
        addedAt: Date.now(),
      })
    })

    if (additions.length > 0) {
      setError(null)
      setPendingUploads(prev => {
        const merged = [...prev, ...additions]
        return merged.map((item, index) => ({ ...item, status: index === 0 ? 'validating' : item.status }))
      })
    }
  }, [activeProfile, notes])

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    handleFiles(event.dataTransfer.files)
  }, [handleFiles])

  const handleBrowse = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const removeUpload = useCallback((id: string) => {
    setPendingUploads(prev => prev.filter(item => item.id !== id))
  }, [])

  const markReady = useCallback(() => {
    if (pendingUploads.length === 0) {
      setError('Add at least one dataset before triggering the pipeline.')
      return
    }

    setPendingUploads(prev => prev.map(item => ({ ...item, status: 'ready' })))
    onOpenAssistant?.('Confirm the import pipeline is ready to run for the latest uploads.')
  }, [pendingUploads.length, onOpenAssistant])

  const recentRuns = useMemo(() => flowRuns.slice(0, 6), [flowRuns])

  const hilStatus = (runId: string) => {
    const approval = hilApprovals[runId]
    if (!approval) return <Badge variant="outline" className="text-muted-foreground">None</Badge>
    switch (approval.status) {
      case 'approved':
        return (
          <Badge variant="outline" className="border-green-500/40 text-green-600 dark:text-green-400">
            <CheckCircle2 className="mr-1 h-3 w-3" /> Approved
          </Badge>
        )
      case 'rejected':
        return (
          <Badge variant="outline" className="border-red-500/40 text-red-600 dark:text-red-400">
            <XCircle className="mr-1 h-3 w-3" /> Rejected
          </Badge>
        )
      default:
        return (
          <Badge variant="outline" className="border-yellow-500/40 text-yellow-700 dark:text-yellow-400">
            <Users className="mr-1 h-3 w-3" /> Waiting
          </Badge>
        )
    }
  }

  const dropZoneClasses = cn(
    'flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-border/80 bg-muted/40 px-6 py-10 text-center transition',
    'hover:border-primary/80 hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
  )

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <CloudUpload className="h-5 w-5" /> Import datasets
          </CardTitle>
          <CardDescription>
            Drag files or browse to kick off refinement. Hotpass validates schema, enforces retention, and surfaces HIL prompts automatically.
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold uppercase text-muted-foreground">Profile</label>
          <div className="flex gap-2">
            {PROFILE_OPTIONS.map(option => (
              <Button
                key={option.value}
                variant={option.value === activeProfile ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveProfile(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={() => onOpenAssistant?.('Which profile should I use for the incoming dataset?')}>
            Ask profile helper
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <section>
          <div
            className={dropZoneClasses}
            tabIndex={0}
            role="button"
            onDragOver={(event) => {
              event.preventDefault()
              event.stopPropagation()
            }}
            onDrop={handleDrop}
            onClick={handleBrowse}
            aria-label="Drop CSV, XLSX, or ZIP files here or press Enter to browse"
          >
            <CloudUpload className="h-10 w-10 text-primary" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium">Drop files to queue them</p>
              <p className="text-xs text-muted-foreground">.csv, .xlsx, and zipped workbooks up to 1GB. Multiple files are supported.</p>
            </div>
            <Button variant="secondary" size="sm" className="mt-2">Browse</Button>
            <Input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".csv,.xlsx,.zip"
              className="hidden"
              onChange={(event) => handleFiles(event.target.files)}
            />
          </div>

          <div className="mt-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Queued uploads</h3>
              <div className="text-xs text-muted-foreground">{pendingUploads.length} selected</div>
            </div>
            {error && (
              <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                <ShieldAlert className="mt-0.5 h-4 w-4" />
                <div>
                  <p className="font-medium">Cannot queue file</p>
                  <p>{error}</p>
                </div>
              </div>
            )}
            {pendingUploads.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/70 bg-muted/30 p-6 text-sm text-muted-foreground">
                No files queued yet. Uploading triggers schema validation and provenance tracking automatically.
              </div>
            ) : (
              <ul className="space-y-3">
                {pendingUploads.map(item => (
                  <li key={item.id} className="rounded-2xl border border-border/70 bg-card/90 p-4 shadow-sm">
                    <div className="flex flex-wrap items-center gap-3">
                      <FileSpreadsheet className="h-5 w-5 text-primary" aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium" title={item.fileName}>{item.fileName}</p>
                        <p className="text-xs text-muted-foreground">{formatBytes(item.size)} • Profile {item.profile}</p>
                      </div>
                      <Badge variant="outline" className={cn('text-xs', {'border-blue-500/50 text-blue-600 dark:text-blue-400': item.status === 'validating', 'border-green-500/50 text-green-600 dark:text-green-400': item.status === 'ready'})}>
                        {item.status === 'validating' ? (
                          <span className="flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Validating</span>
                        ) : item.status === 'ready' ? 'Ready for pipeline' : 'Queued'}
                      </Badge>
                      <Button variant="ghost" size="sm" onClick={() => removeUpload(item.id)}>Remove</Button>
                    </div>
                    {item.hasNotes && (
                      <p className="mt-3 text-xs text-muted-foreground">Operator notes will accompany this upload.</p>
                    )}
                    <p className="mt-2 text-[11px] uppercase text-muted-foreground">Added {formatDistanceToNow(item.addedAt, { addSuffix: true })}</p>
                  </li>
                ))}
              </ul>
            )}

            <div className="space-y-3">
              <label htmlFor="import-notes" className="text-xs font-semibold uppercase text-muted-foreground">Operator notes (optional)</label>
              <textarea
                id="import-notes"
                className="h-24 w-full rounded-2xl border border-border/70 bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                placeholder="Add context for reviewers (e.g. source system, requested transformations, data quirks)."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                Uploads are encrypted in transit and stored in region-matched buckets. Provenance metadata is appended on ingest.
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setPendingUploads([])}>Clear</Button>
                <Button size="sm" className="gap-2" onClick={markReady}>
                  <ArrowRightCircle className="h-4 w-4" />
                  Trigger refine pipeline
                </Button>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="rounded-3xl border border-border/80 bg-muted/40 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Activity className="h-4 w-4" /> Live process timeline
            </div>
            <p className="mt-1 text-xs text-muted-foreground">Prefect status and HIL state update in real-time. Click a row to inspect the run.</p>
          </div>

          <div className="space-y-3">
            {isLoadingRuns ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                Loading recent runs…
              </div>
            ) : recentRuns.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/60 bg-background/70 p-4 text-xs text-muted-foreground">
                No recent runs yet. Upload a dataset or check Prefect connectivity.
              </div>
            ) : (
              <ul className="space-y-3">
                {recentRuns.map(run => {
                  const profile = typeof run.parameters?.profile === 'string'
                    ? run.parameters.profile as string
                    : undefined
                  const durationSeconds = typeof run.total_run_time === 'number'
                    ? Math.max(0, Math.round(run.total_run_time))
                    : 0

                  return (
                    <li key={run.id} className="rounded-2xl border border-border/70 bg-card/90 p-4">
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold" title={run.name}>{run.name}</p>
                          <p className="text-xs text-muted-foreground">Started {run.start_time ? formatDistanceToNow(new Date(run.start_time), { addSuffix: true }) : '—'} • {formatDuration(durationSeconds)}</p>
                          {profile && (
                            <p className="text-[11px] uppercase text-muted-foreground">Profile {profile}</p>
                          )}
                        </div>
                        <Badge variant="outline" className={cn('text-xs', getStatusColor(run.state_name))}>
                          {run.state_name}
                        </Badge>
                        {hilStatus(run.id)}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onOpenAssistant?.(`Explain the status of Prefect run ${run.name}`)}
                        >
                          Insights
                        </Button>
                      </div>
                    {run.hil_comment && (
                      <p className="mt-2 text-xs text-muted-foreground">Latest HIL note: {run.hil_comment}</p>
                    )}
                  </li>
                  )
                })}
              </ul>
            )}
          </div>

          <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-2 font-medium text-sm">
              <Files className="h-4 w-4" /> Best practices
            </div>
            <ul className="mt-2 space-y-1">
              <li>• Group related files to keep lineage tidy.</li>
              <li>• Use notes to flag upstream anomalies or stakeholder context.</li>
              <li>• HIL waits on you? Approve or request follow-up from the dashboard table.</li>
            </ul>
          </div>
        </section>
      </CardContent>
    </Card>
  )
}
