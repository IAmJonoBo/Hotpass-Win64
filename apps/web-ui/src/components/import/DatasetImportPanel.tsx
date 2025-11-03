import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import type { PrefectFlowRun, HILApproval, ImportIssueSeverity, ImportProfile } from '@/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn, formatBytes, formatDuration, getStatusColor } from '@/lib/utils'
import { useImportProfileMutation } from '@/api/imports'
import { LiveProcessingWidget, type LiveProcessingSnapshot } from '@/components/import/LiveProcessingWidget'

type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'
type ImportStage = 'queued' | 'upload-complete' | 'refine-started' | 'completed' | 'failed'
type StageVisualState = 'pending' | 'active' | 'complete' | 'failed'

interface JobSummary {
  id: string
  status: JobStatus
  label?: string
  createdAt?: string
  updatedAt?: string
  startedAt?: string
  completedAt?: string
  metadata?: Record<string, unknown>
  exitCode?: number | null
  error?: string | null
}

interface UploadFileMetadata {
  originalName: string
  filename: string
  size: number
  mimetype?: string
}

interface ImportArtifact {
  id: string
  name: string
  kind: 'refined' | 'archive' | 'profile'
  size: number
  url: string
}

interface ImportJobState {
  job: JobSummary
  stage: ImportStage
  files: UploadFileMetadata[]
  artifacts: ImportArtifact[]
  logs: string[]
  error?: string
}

interface DatasetImportPanelProps {
  flowRuns: PrefectFlowRun[]
  hilApprovals: Record<string, HILApproval>
  isLoadingRuns: boolean
  onOpenAssistant?: (message?: string) => void
}

interface PendingUpload {
  id: string
  file: File
  profile: string
  status: 'queued'
  addedAt: number
}

const PROFILE_OPTIONS = [
  { value: 'generic', label: 'Generic' },
  { value: 'aviation', label: 'Aviation' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'enrichment', label: 'Enrichment + network' },
]

const MAX_LOG_LINES = 200

const IMPORT_STAGES: Array<{ id: ImportStage; label: string; description?: string }> = [
  { id: 'queued', label: 'Queued', description: 'Preparing upload workspace' },
  { id: 'upload-complete', label: 'Upload processed', description: 'Files staged for refinement' },
  { id: 'refine-started', label: 'Refining', description: 'Executing hotpass refine pipeline' },
  { id: 'completed', label: 'Completed', description: 'Artifacts available for download' },
]

const STAGE_STYLES: Record<StageVisualState, { container: string; icon: string }> = {
  pending: {
    container: 'border-border/60 bg-muted/40 text-muted-foreground',
    icon: 'text-muted-foreground',
  },
  active: {
    container: 'border-primary/60 bg-primary/10 text-primary',
    icon: 'text-primary',
  },
  complete: {
    container: 'border-green-500/40 bg-green-500/10 text-green-600 dark:text-green-400',
    icon: 'text-green-600 dark:text-green-400',
  },
  failed: {
    container: 'border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400',
    icon: 'text-red-600 dark:text-red-400',
  },
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const isImportStage = (value: unknown): value is ImportStage =>
  typeof value === 'string' && IMPORT_STAGES.some(stage => stage.id === value)

const importStageIndex = (stage: ImportStage) =>
  IMPORT_STAGES.findIndex(item => item.id === stage)

const sanitizeFiles = (value: unknown): UploadFileMetadata[] => {
  if (!Array.isArray(value)) return []
  const files: UploadFileMetadata[] = []
  value.forEach(item => {
    if (!isRecord(item)) return
    const originalName =
      typeof item.originalName === 'string'
        ? item.originalName
        : typeof item.filename === 'string'
          ? item.filename
          : 'dataset'
    const filename = typeof item.filename === 'string' ? item.filename : originalName
    const size = typeof item.size === 'number' && Number.isFinite(item.size) ? item.size : 0
    const mimetype = typeof item.mimetype === 'string' ? item.mimetype : undefined
    files.push({ originalName, filename, size, mimetype })
  })
  return files
}

const sanitizeArtifacts = (value: unknown): ImportArtifact[] => {
  if (!Array.isArray(value)) return []
  const artifacts: ImportArtifact[] = []
  value.forEach(item => {
    if (!isRecord(item)) return
    const id = typeof item.id === 'string' ? item.id : undefined
    const name = typeof item.name === 'string' ? item.name : undefined
    const kindRaw = typeof item.kind === 'string' ? item.kind : undefined
    const url = typeof item.url === 'string' ? item.url : undefined
    if (!id || !name || !url) return
    if (!['refined', 'archive', 'profile'].includes(kindRaw)) return
    const size = typeof item.size === 'number' && Number.isFinite(item.size) ? item.size : 0
    artifacts.push({ id, name, kind: kindRaw as ImportArtifact['kind'], url, size })
  })
  return artifacts
}

const isJobSummary = (value: unknown): value is JobSummary =>
  isRecord(value) &&
  typeof value.id === 'string' &&
  typeof value.status === 'string'

const deriveStage = (job: JobSummary, previous?: ImportStage): ImportStage => {
  if (job.status === 'succeeded') return 'completed'
  if (job.status === 'failed') return 'failed'
  const metadataStage = isRecord(job.metadata) && typeof job.metadata.stage === 'string' ? job.metadata.stage : undefined
  if (metadataStage && isImportStage(metadataStage)) {
    return metadataStage
  }
  return previous ?? 'queued'
}

const appendLogs = (logs: string[], stream: 'stdout' | 'stderr', message: string): string[] => {
  const normalized = message.replace(/\r\n/g, '\n')
  const segments = normalized.split('\n').map(segment => segment.trimEnd()).filter(segment => segment.length > 0)
  if (segments.length === 0) return logs
  const prefix = stream === 'stderr' ? 'stderr' : 'stdout'
  const appended = logs.concat(segments.map(segment => `[${prefix}] ${segment}`))
  return appended.slice(-MAX_LOG_LINES)
}

const resolveStageVisualState = (currentStage: ImportStage, stageId: ImportStage, status: JobStatus): StageVisualState => {
  if (currentStage === 'failed') {
    if (stageId === 'completed') {
      return 'failed'
    }
    return 'complete'
  }

  const currentIndex = importStageIndex(currentStage)
  const targetIndex = importStageIndex(stageId)

  if (currentIndex === -1 || targetIndex === -1) {
    return 'pending'
  }

  if (targetIndex < currentIndex) {
    return 'complete'
  }

  if (targetIndex === currentIndex) {
    if (status === 'succeeded') return 'complete'
    return status === 'running' ? 'active' : 'complete'
  }

  return 'pending'
}

const ISSUE_SEVERITY_STYLES: Record<ImportIssueSeverity, string> = {
  info: 'border-blue-500/40 text-blue-600 dark:text-blue-400',
  warning: 'border-yellow-500/50 text-yellow-700 dark:text-yellow-400',
  error: 'border-red-500/50 text-red-600 dark:text-red-400',
}

export function DatasetImportPanel({ flowRuns, hilApprovals, isLoadingRuns, onOpenAssistant }: DatasetImportPanelProps) {
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
  const [activeProfile, setActiveProfile] = useState(PROFILE_OPTIONS[0].value)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [csrfError, setCsrfError] = useState<string | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [importJob, setImportJob] = useState<ImportJobState | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [csrfToken, setCsrfToken] = useState<string | null>(null)
  const [profilePreview, setProfilePreview] = useState<ImportProfile | null>(null)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [shouldAttachProfile, setShouldAttachProfile] = useState(true)
  const [previewSourceName, setPreviewSourceName] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const jobStateRef = useRef<ImportJobState | null>(null)
  const profileKeyRef = useRef<string | null>(null)

  const totalUploadSize = useMemo(
    () => pendingUploads.reduce((acc, upload) => acc + upload.file.size, 0),
    [pendingUploads],
  )

  const recentRuns = useMemo(() => flowRuns.slice(0, 6), [flowRuns])
  const primaryUpload = pendingUploads[0] ?? null

  const { mutateAsync: runProfile, reset: resetProfile, isPending: isProfiling } = useImportProfileMutation()

  const jobStatus = importJob?.job.status ?? null
  const jobInFlight = jobStatus === 'running' || jobStatus === 'queued'
  const disableInputs = isSubmitting || jobInFlight
  const hasPendingUploads = pendingUploads.length > 0

  useEffect(() => {
    jobStateRef.current = importJob
  }, [importJob])

  useEffect(() => () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }, [])

  useEffect(() => {
    if (pendingUploads.length === 0) {
      profileKeyRef.current = null
      setProfilePreview(null)
      setProfileError(null)
      setPreviewSourceName(null)
      resetProfile()
      return
    }

    const primary = pendingUploads[0]
    const key = `${primary.file.name}-${primary.file.size}-${primary.file.lastModified}`
    if (profileKeyRef.current === key && profilePreview) {
      return
    }

    profileKeyRef.current = key
    setShouldAttachProfile(true)
    setProfilePreview(null)
    setProfileError(null)
    setPreviewSourceName(primary.file.name)

    let cancelled = false

    runProfile({ file: primary.file })
      .then((profile) => {
        if (!cancelled) {
          setProfilePreview(profile)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setProfileError(error instanceof Error ? error.message : 'Failed to profile workbook')
        }
      })

    return () => {
      cancelled = true
    }
  }, [pendingUploads, profilePreview, resetProfile, runProfile])

  const updateImportJob = useCallback((updater: (prev: ImportJobState | null) => ImportJobState | null) => {
    setImportJob(prev => {
      const next = updater(prev)
      jobStateRef.current = next
      return next
    })
  }, [])

  const getCsrfToken = useCallback(async (opts?: { silent?: boolean }): Promise<string | null> => {
    if (csrfToken) {
      return csrfToken
    }

    try {
      const response = await fetch('/telemetry/operator-feedback/csrf', {
        method: 'GET',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      if (typeof data.token === 'string' && data.token.length > 0) {
        setCsrfToken(data.token)
        if (!opts?.silent) {
          setCsrfError(null)
        }
        return data.token
      }

      throw new Error('Missing token in response')
    } catch {
      if (!opts?.silent) {
        setCsrfError('Unable to initialise secure session. Please refresh and try again.')
      }
      return null
    }
  }, [csrfToken])

  useEffect(() => {
    getCsrfToken({ silent: true }).catch(() => undefined)
  }, [getCsrfToken])

  const connectToJob = useCallback((jobId: string) => {
    const open = () => {
      eventSourceRef.current?.close()
      const encodedId = encodeURIComponent(jobId)
      const eventSource = new EventSource(`/api/jobs/${encodedId}/events`)
      eventSourceRef.current = eventSource
      setConnectionError(null)

      const parseEvent = (event: MessageEvent): Record<string, unknown> | null => {
        try {
          const data = JSON.parse(event.data) as Record<string, unknown>
          return data
        } catch (parseError) {
          console.warn('Failed to parse import event payload', parseError)
          return null
        }
      }

      eventSource.addEventListener('snapshot', (event) => {
        const data = parseEvent(event)
        if (!data || !isJobSummary(data.job)) {
          return
        }

        const job = data.job
        const files = sanitizeFiles(job.metadata?.files)
        const artifacts = sanitizeArtifacts(job.metadata?.artifacts)
        const stage = deriveStage(job, jobStateRef.current?.stage)

        updateImportJob(prev => ({
          job,
          stage,
          files: files.length > 0 ? files : prev?.files ?? [],
          artifacts: artifacts.length > 0 ? artifacts : prev?.artifacts ?? [],
          logs: prev?.logs ?? [],
          error: job.error ?? prev?.error,
        }))
      })

      eventSource.addEventListener('stage', (event) => {
        const data = parseEvent(event)
        if (!data) return
        updateImportJob(prev => {
          if (!prev) return prev
          const stage = isImportStage(data.stage) ? data.stage : prev.stage
          return {
            ...prev,
            stage,
            job: {
              ...prev.job,
              metadata: {
                ...(prev.job.metadata ?? {}),
                stage,
              },
            },
          }
        })
      })

      eventSource.addEventListener('file-accepted', (event) => {
        const data = parseEvent(event)
        if (!data) return
        const accepted = sanitizeFiles(data.file ? [data.file] : undefined)
        if (accepted.length === 0) return
        updateImportJob(prev => {
          if (!prev) return prev
          const merged = [...prev.files]
          accepted.forEach(file => {
            if (!merged.some(existing => existing.filename === file.filename)) {
              merged.push(file)
            }
          })
          return {
            ...prev,
            files: merged,
          }
        })
      })

      eventSource.addEventListener('log', (event) => {
        const data = parseEvent(event)
        const logMessage = data && typeof data.message === 'string' ? data.message : null
        if (!logMessage) return
        const stream: 'stdout' | 'stderr' = data?.stream === 'stderr' ? 'stderr' : 'stdout'
        updateImportJob(prev => {
          if (!prev) return prev
          return {
            ...prev,
            logs: appendLogs(prev.logs, stream, logMessage),
          }
        })
      })

      eventSource.addEventListener('artifact-ready', (event) => {
        const data = parseEvent(event)
        if (!data) return
        const artifacts = sanitizeArtifacts(data.artifacts)
        if (artifacts.length === 0) return
        updateImportJob(prev => {
          if (!prev) return prev
          return {
            ...prev,
            artifacts,
            job: {
              ...prev.job,
              metadata: {
                ...(prev.job.metadata ?? {}),
                artifacts,
              },
            },
          }
        })
      })

      eventSource.addEventListener('error', () => {
        updateImportJob(prev => {
          if (!prev) return prev
          return {
            ...prev,
            error: prev.error ?? 'Stream connection interrupted',
          }
        })
      })

      eventSource.addEventListener('finished', (event) => {
        const data = parseEvent(event)
        updateImportJob(prev => {
          if (!prev) return prev
          const nextStatus = typeof data?.status === 'string' ? (data.status as JobStatus) : prev.job.status
          const stage =
            nextStatus === 'succeeded'
              ? 'completed'
              : nextStatus === 'failed'
                ? 'failed'
                : prev.stage
          return {
            ...prev,
            stage,
            job: {
              ...prev.job,
              status: nextStatus,
              completedAt:
                typeof data?.completedAt === 'string'
                  ? data.completedAt
                  : prev.job.completedAt ?? new Date().toISOString(),
              exitCode:
                typeof data?.exitCode === 'number'
                  ? data.exitCode
                  : prev.job.exitCode,
            },
            error:
              nextStatus === 'failed'
                ? typeof data?.error === 'string'
                  ? data.error
                  : prev.error ?? prev.job.error ?? 'Import failed'
                : prev.error,
          }
        })
        eventSource.close()
        if (eventSourceRef.current === eventSource) {
          eventSourceRef.current = null
        }
      })

      eventSource.onerror = () => {
        eventSource.close()
        if (eventSourceRef.current === eventSource) {
          eventSourceRef.current = null
        }
        const current = jobStateRef.current
        if (current && (current.job.status === 'running' || current.job.status === 'queued')) {
          setConnectionError('Connection lost. Retrying…')
          window.setTimeout(() => {
            if (jobStateRef.current && (jobStateRef.current.job.status === 'running' || jobStateRef.current.job.status === 'queued')) {
              open()
            }
          }, 2000)
        }
      }
    }

    open()
  }, [updateImportJob])

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return

    const maxFileSize = 1_000_000_000 // 1GB
    const allowedExtensions = ['.csv', '.xlsx', '.zip']
    const allowedMimeTypes = [
      'text/csv',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/zip',
    ]

    const additions: PendingUpload[] = []

    Array.from(fileList).forEach(file => {
      const lowerName = file.name.toLowerCase()
      const hasAllowedExtension = allowedExtensions.some(ext => lowerName.endsWith(ext))
      const hasAllowedMime = allowedMimeTypes.includes(file.type)
      if (file.size > maxFileSize) {
        setError(`"${file.name}" exceeds the 1GB limit. Split the dataset or compress it before retrying.`)
        return
      }
      if (!hasAllowedExtension && !hasAllowedMime) {
        setError(`"${file.name}" is not a supported format. Upload CSV, XLSX, or ZIP bundles.`)
        return
      }

      additions.push({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        profile: activeProfile,
        status: 'queued',
        addedAt: Date.now(),
      })
    })

    if (additions.length > 0) {
      setError(null)
      setSubmissionError(null)
      setCsrfError(null)
      setPendingUploads(prev => [...prev, ...additions])
    }
  }, [activeProfile])

  const removeUpload = useCallback((id: string) => {
    setPendingUploads(prev => prev.filter(item => item.id !== id))
  }, [])

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    if (disableInputs) return
    handleFiles(event.dataTransfer.files)
  }, [disableInputs, handleFiles])

  const handleBrowse = useCallback(() => {
    if (disableInputs) return
    fileInputRef.current?.click()
  }, [disableInputs])

  const clearPendingUploads = useCallback(() => {
    setPendingUploads([])
    setProfilePreview(null)
    setProfileError(null)
    setPreviewSourceName(null)
    setShouldAttachProfile(true)
    profileKeyRef.current = null
    resetProfile()
  }, [resetProfile])

  const handleDownloadProfile = useCallback(() => {
    if (!profilePreview) return
    const baseName = (previewSourceName ?? profilePreview.workbook ?? 'import-profile')
      .toString()
      .replace(/[^a-z0-9-_]+/gi, '_')
      .replace(/_{2,}/g, '_')
      .replace(/^_+|_+$/g, '')
      .slice(0, 64) || 'import-profile'
    const blob = new Blob([JSON.stringify(profilePreview, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${baseName}-profile.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [previewSourceName, profilePreview])

  const handleReprofile = useCallback(() => {
    if (!pendingUploads.length || isProfiling) {
      return
    }
    const primary = pendingUploads[0]
    const key = `${primary.file.name}-${primary.file.size}-${primary.file.lastModified}`
    profileKeyRef.current = key
    setProfilePreview(null)
    setProfileError(null)
    setPreviewSourceName(primary.file.name)
    runProfile({ file: primary.file })
      .then((profile) => {
        setProfilePreview(profile)
      })
      .catch((error) => {
        setProfileError(error instanceof Error ? error.message : 'Failed to profile workbook')
      })
  }, [isProfiling, pendingUploads, runProfile])

  const startImport = useCallback(async () => {
    if (pendingUploads.length === 0) {
      setError('Add at least one dataset before triggering the pipeline.')
      return
    }

    if (disableInputs && !jobInFlight) {
      return
    }

    if (shouldAttachProfile && !profilePreview) {
      setSubmissionError('Profiling still running. Wait for the preview or disable attachment before starting the import.')
      return
    }

    setError(null)
    setSubmissionError(null)
    setConnectionError(null)
    setIsSubmitting(true)

    try {
      const token = await getCsrfToken()
      if (!token) {
        setSubmissionError('Unable to obtain secure session token. Please refresh and try again.')
        return
      }

      const formData = new FormData()
      pendingUploads.forEach(upload => {
        formData.append('files', upload.file, upload.file.name)
      })
      formData.append('profile', activeProfile)
      if (notes.trim().length > 0) {
        formData.append('notes', notes.trim())
      }
      const includeProfileAttachment = shouldAttachProfile && Boolean(profilePreview)
      formData.append('attachProfile', includeProfileAttachment ? 'true' : 'false')
      if (includeProfileAttachment && profilePreview) {
        formData.append('profilePayload', JSON.stringify(profilePreview))
        if (previewSourceName) {
          formData.append('profileSourceName', previewSourceName)
        }
      }

      const response = await fetch('/api/import', {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRF-Token': token,
        },
        credentials: 'include',
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setSubmissionError(typeof body.error === 'string' ? body.error : 'Failed to start import')
        return
      }

      const payload = await response.json()
      if (!isRecord(payload) || !isJobSummary(payload.job)) {
        setSubmissionError('Unexpected response from server.')
        return
      }

      const job = payload.job
      const filesFromMetadata = sanitizeFiles(job.metadata?.files)
      const artifactsFromMetadata = sanitizeArtifacts(job.metadata?.artifacts)
      const initialFiles =
        filesFromMetadata.length > 0
          ? filesFromMetadata
          : pendingUploads.map(upload => ({
              originalName: upload.file.name,
              filename: upload.file.name,
              size: upload.file.size,
              mimetype: upload.file.type,
            }))

      const nextJobState: ImportJobState = {
        job,
        stage: deriveStage(job),
        files: initialFiles,
        artifacts: artifactsFromMetadata,
        logs: [],
      }

      updateImportJob(() => nextJobState)
      setPendingUploads([])
      setNotes('')
      setProfilePreview(null)
      setProfileError(null)
      setPreviewSourceName(null)
      setShouldAttachProfile(true)
      profileKeyRef.current = null
      connectToJob(job.id)
    } catch (startError) {
      console.error('[import] request failed', startError)
      setSubmissionError(startError instanceof Error ? startError.message : 'Failed to submit import request')
    } finally {
      setIsSubmitting(false)
    }
  }, [
    pendingUploads,
    activeProfile,
    notes,
    shouldAttachProfile,
    profilePreview,
    previewSourceName,
    disableInputs,
    jobInFlight,
    getCsrfToken,
    updateImportJob,
    connectToJob,
  ])

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [])

  const hilStatus = useCallback((runId: string) => {
    const approval = hilApprovals[runId]
    if (!approval) {
      return <Badge variant="outline" className="text-muted-foreground">None</Badge>
    }
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
  }, [hilApprovals])

  const dropZoneClasses = cn(
    'relative flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed border-border/80 bg-muted/40 px-6 py-10 text-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
    'hover:border-primary/80 hover:bg-muted/80',
    disableInputs && 'pointer-events-none opacity-60',
  )

  const refinedArtifact = importJob?.artifacts.find(artifact => artifact.kind === 'refined') ?? null
  const profileArtifact = importJob?.artifacts.find(artifact => artifact.kind === 'profile') ?? null
  const jobMetadata = isRecord(importJob?.job.metadata) ? (importJob.job.metadata as Record<string, unknown>) : null
  const jobNotes = jobMetadata && typeof jobMetadata['notes'] === 'string'
    ? (jobMetadata['notes'] as string)
    : null

  const profileSheetCount = useMemo(() => {
    if (!profilePreview) return undefined
    return profilePreview.sheets.length
  }, [profilePreview])

  const profileTotalRows = useMemo(() => {
    if (!profilePreview) return undefined
    return profilePreview.sheets.reduce((acc, sheet) => acc + (typeof sheet.rows === 'number' ? sheet.rows : 0), 0)
  }, [profilePreview])

  const fallbackWorkbookName = useMemo(() => {
    if (profilePreview?.workbook) return String(profilePreview.workbook)
    if (primaryUpload) return primaryUpload.file.name
    if (jobMetadata && typeof jobMetadata['workbook'] === 'string') return jobMetadata['workbook'] as string
    return importJob?.job.label ?? null
  }, [jobMetadata, importJob?.job.label, primaryUpload, profilePreview?.workbook])

  const liveProcessingSnapshot: LiveProcessingSnapshot | null = useMemo(() => {
    if (!importJob) return null
    return {
      id: importJob.job.id,
      label: importJob.job.label ?? undefined,
      status: importJob.job.status,
      stage: importJob.stage,
      startedAt: importJob.job.startedAt,
      updatedAt: importJob.job.updatedAt,
      completedAt: importJob.job.completedAt,
      logs: importJob.logs,
      error: importJob.error ?? null,
      metadata: jobMetadata ?? undefined,
    }
  }, [importJob, jobMetadata])

  const statusBadgeStyle =
    jobStatus === 'succeeded'
      ? 'border-green-500/40 bg-green-500/10 text-green-600 dark:text-green-400'
      : jobStatus === 'failed'
        ? 'border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400'
        : 'border-blue-500/40 bg-blue-500/10 text-blue-600 dark:text-blue-400'

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
                disabled={disableInputs && option.value !== activeProfile}
              >
                {option.label}
              </Button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOpenAssistant?.('Which profile should I use for the incoming dataset?')}
          >
            Ask profile helper
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-8 lg:grid-cols-[1.4fr_1fr]">
        <section>
          <div
            className={dropZoneClasses}
            tabIndex={disableInputs ? -1 : 0}
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
              <p className="text-sm font-medium">{disableInputs ? 'Import in progress' : 'Drop files to queue them'}</p>
              <p className="text-xs text-muted-foreground">.csv, .xlsx, and zipped workbooks up to 1GB. Multiple files supported.</p>
            </div>
            <Button variant="secondary" size="sm" className="mt-2" disabled={disableInputs}>
              Browse
            </Button>
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
            {(error || submissionError || csrfError) && (
              <div className="space-y-2">
                {error && (
                  <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Cannot queue file</p>
                      <p>{error}</p>
                    </div>
                  </div>
                )}
                {submissionError && (
                  <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Import request failed</p>
                      <p>{submissionError}</p>
                    </div>
                  </div>
                )}
                {csrfError && (
                  <div className="flex items-start gap-3 rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-700 dark:text-yellow-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Security token missing</p>
                      <p>{csrfError}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Queued uploads</h3>
              <div className="text-xs text-muted-foreground">
                {pendingUploads.length === 0 ? 'No files queued' : `${pendingUploads.length} selected (${formatBytes(totalUploadSize)})`}
              </div>
            </div>

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
                        <p className="truncate text-sm font-medium" title={item.file.name}>{item.file.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatBytes(item.file.size)} • Added {formatDistanceToNow(item.addedAt, { addSuffix: true })}
                        </p>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => removeUpload(item.id)} disabled={disableInputs}>
                        Remove
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {pendingUploads.length > 0 && (
              <div className="space-y-3 rounded-2xl border border-dashed border-border/70 bg-muted/25 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">Profiling preview</p>
                    <p className="text-xs text-muted-foreground">
                      {primaryUpload
                        ? `Based on ${primaryUpload.file.name} (${formatBytes(primaryUpload.file.size)})`
                        : 'Drop a workbook to generate a profile.'}
                    </p>
                    <p className="text-[11px] text-muted-foreground/80">
                      Preview covers the first file in the queue; additional files profile during the guided wizard.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {isProfiling && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Profiling…
                      </span>
                    )}
                    <Button variant="ghost" size="sm" onClick={handleReprofile} disabled={!primaryUpload || isProfiling}>
                      Re-run
                    </Button>
                  </div>
                </div>
                {profileError ? (
                  <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Profiling failed</p>
                      <p>{profileError}</p>
                    </div>
                  </div>
                ) : profilePreview ? (
                  <>
                    {profilePreview.issues && profilePreview.issues.length > 0 && (
                      <div className="space-y-1 text-xs">
                        {profilePreview.issues.slice(0, 3).map((issue, index) => (
                          <div
                            key={`${issue.code ?? issue.message}-${index}`}
                            className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/90 px-3 py-2"
                          >
                            <span
                              className={cn(
                                'rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                                ISSUE_SEVERITY_STYLES[issue.severity],
                              )}
                            >
                              {issue.severity}
                            </span>
                            <span className="flex-1">{issue.message}</span>
                          </div>
                        ))}
                        {profilePreview.issues.length > 3 && (
                          <p className="text-[11px] text-muted-foreground">
                            +{profilePreview.issues.length - 3} additional workbook issues
                          </p>
                        )}
                      </div>
                    )}
                    <div className="grid gap-3 md:grid-cols-2">
                      {profilePreview.sheets.map((sheet) => {
                        const columnSample = sheet.columns.slice(0, 3)
                        return (
                          <div key={sheet.name} className="rounded-2xl border border-border/70 bg-card/80 p-4">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <p className="text-sm font-semibold">{sheet.name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {sheet.rows.toLocaleString()} rows · {sheet.columns.length} columns
                                </p>
                              </div>
                              <Badge variant="outline" className="text-xs capitalize">
                                {sheet.role || 'unknown'}
                              </Badge>
                            </div>
                            {sheet.joinKeys.length > 0 && (
                              <p className="mt-3 text-[11px] text-muted-foreground">
                                <span className="font-medium text-foreground">Join keys:</span>{' '}
                                {sheet.joinKeys.join(', ')}
                              </p>
                            )}
                            <div className="mt-3 space-y-1 text-xs">
                              {columnSample.map(column => (
                                <div
                                  key={column.name}
                                  className="flex items-center justify-between gap-2 rounded-lg border border-border/60 bg-background/80 px-2 py-1"
                                >
                                  <span className="truncate font-medium" title={column.name}>{column.name}</span>
                                  <span className="text-muted-foreground">{column.inferredType}</span>
                                </div>
                              ))}
                              {sheet.columns.length > columnSample.length && (
                                <p className="text-[11px] text-muted-foreground">
                                  +{sheet.columns.length - columnSample.length} more columns
                                </p>
                              )}
                              {sheet.issues.length > 0 && (
                                <div className="pt-2 text-[11px] text-muted-foreground">
                                  {sheet.issues.slice(0, 2).map((issue, index) => (
                                    <div key={`${sheet.name}-issue-${index}`} className="flex items-start gap-2">
                                      <span
                                        className={cn(
                                          'mt-0.5 h-2 w-2 rounded-full',
                                          issue.severity === 'error'
                                            ? 'bg-red-500'
                                            : issue.severity === 'warning'
                                              ? 'bg-yellow-500'
                                              : 'bg-blue-500',
                                        )}
                                      />
                                      <span>{issue.message}</span>
                                    </div>
                                  ))}
                                  {sheet.issues.length > 2 && (
                                    <p>+{sheet.issues.length - 2} more sheet issues</p>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Drop a workbook to preview inferred schema, join keys, and quality signals before running refinement.
                  </p>
                )}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-3">
                  <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border border-border/70 bg-background text-primary focus:ring-2 focus:ring-primary focus:ring-offset-1"
                      checked={shouldAttachProfile}
                      onChange={(event) => setShouldAttachProfile(event.target.checked)}
                    />
                    Attach profiling JSON to import job artifacts
                  </label>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={handleDownloadProfile} disabled={!profilePreview}>
                      Download JSON
                    </Button>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-3">
              <label htmlFor="import-notes" className="text-xs font-semibold uppercase text-muted-foreground">Operator notes (optional)</label>
              <textarea
                id="import-notes"
                className="h-24 w-full rounded-2xl border border-border/70 bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                placeholder="Add context for reviewers (e.g. source system, requested transformations, data quirks)."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                disabled={disableInputs}
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">
                Uploads are encrypted in transit and stored in region-matched buckets. Provenance metadata is appended on ingest.
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearPendingUploads}
                  disabled={!hasPendingUploads || disableInputs}
                >
                  Clear
                </Button>
                <Button
                  size="sm"
                  className="gap-2"
                  onClick={startImport}
                  disabled={!hasPendingUploads || disableInputs}
                >
                  {(isSubmitting || jobInFlight) ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {jobInFlight ? 'Import running…' : 'Uploading…'}
                    </>
                  ) : (
                    <>
                      <ArrowRightCircle className="h-4 w-4" />
                      Start import
                    </>
                  )}
                </Button>
              </div>
            </div>

            {importJob && (
              <div className="space-y-4 border-t border-border/60 pt-4">
                {importJob.job.status === 'failed' && importJob.error && (
                  <div className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Import failed</p>
                      <p>{importJob.error}</p>
                    </div>
                  </div>
                )}
                {connectionError && (
                  <div className="flex items-start gap-3 rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-700 dark:text-yellow-400">
                    <ShieldAlert className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="font-medium">Connection issue</p>
                      <p>{connectionError}</p>
                    </div>
                  </div>
                )}
                <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{importJob.job.label ?? 'Hotpass refine job'}</p>
                      <p className="text-xs text-muted-foreground">
                        Job ID {importJob.job.id} · Started{' '}
                        {importJob.job.startedAt
                          ? formatDistanceToNow(new Date(importJob.job.startedAt), { addSuffix: true })
                          : '—'}
                      </p>
                    </div>
                    <Badge variant="outline" className={cn('text-xs px-3 py-1', statusBadgeStyle)}>
                      {jobStatus === 'succeeded'
                        ? 'Completed'
                        : jobStatus === 'failed'
                          ? 'Failed'
                          : 'In progress'}
                    </Badge>
                  </div>
                  <div className="mt-4">
                    <LiveProcessingWidget
                      job={liveProcessingSnapshot}
                      profile={profilePreview}
                      workbookName={fallbackWorkbookName}
                      sheetCount={profileSheetCount}
                      totalRows={profileTotalRows}
                      refreshIntervalMs={300}
                    />
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-4">
                    {IMPORT_STAGES.map(stage => {
                      const visualState = resolveStageVisualState(importJob.stage, stage.id, importJob.job.status)
                      const palette = STAGE_STYLES[visualState]
                      const Icon =
                        visualState === 'complete'
                          ? CheckCircle2
                          : visualState === 'failed'
                            ? XCircle
                            : visualState === 'active'
                              ? Loader2
                              : Activity
                      return (
                        <div
                          key={stage.id}
                          className={cn(
                            'rounded-2xl border px-3 py-3 text-left transition',
                            palette.container,
                          )}
                        >
                          <div className="flex items-center gap-2 text-sm font-medium">
                            <Icon className={cn('h-4 w-4', palette.icon, visualState === 'active' && 'animate-spin')} />
                            {stage.label}
                          </div>
                          {stage.description && (
                            <p className="mt-1 text-xs text-muted-foreground">{stage.description}</p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
                  <p className="text-sm font-semibold">Uploaded files</p>
                  {importJob.files.length === 0 ? (
                    <p className="mt-2 text-xs text-muted-foreground">Files will appear once the import starts.</p>
                  ) : (
                    <ul className="mt-3 space-y-2">
                      {importJob.files.map(file => (
                        <li key={file.filename} className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="truncate pr-3">{file.originalName}</span>
                          <span>{formatBytes(file.size)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {jobNotes && (
                  <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
                    <p className="text-sm font-semibold">Operator notes</p>
                    <p className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap">{jobNotes}</p>
                  </div>
                )}

                <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold">Artifacts</p>
                    {refinedArtifact && (
                      <span className="text-xs text-muted-foreground">
                        Refined workbook ready ({formatBytes(refinedArtifact.size)})
                      </span>
                    )}
                    {!refinedArtifact && profileArtifact && (
                      <span className="text-xs text-muted-foreground">
                        Profiling JSON attached ({formatBytes(profileArtifact.size)})
                      </span>
                    )}
                  </div>
                  {importJob.artifacts.length === 0 ? (
                    <p className="mt-2 text-xs text-muted-foreground">Artifacts will appear once the job completes.</p>
                  ) : (
                    <ul className="mt-3 space-y-2">
                      {importJob.artifacts.map(artifact => (
                        <li key={artifact.id} className="flex items-center justify-between rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs">
                          <div className="flex flex-col">
                            <span className="font-medium text-foreground">{artifact.name}</span>
                            <span className="text-muted-foreground">
                              {artifact.kind === 'refined'
                                ? 'Refined workbook'
                                : artifact.kind === 'archive'
                                  ? 'Archive bundle'
                                  : 'Profiling JSON'} · {formatBytes(artifact.size)}
                            </span>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => window.open(artifact.url, '_blank', 'noreferrer')}
                          >
                            Download
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="rounded-2xl border border-border/70 bg-card/90 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold">Logs</p>
                    <span className="text-xs text-muted-foreground">{importJob.logs.length} lines</span>
                  </div>
                  <div className="mt-2 max-h-48 overflow-y-auto rounded-xl bg-background/90 p-3 font-mono text-xs">
                    {importJob.logs.length === 0 ? (
                      <p className="text-muted-foreground">Logs will appear once the pipeline starts.</p>
                    ) : (
                      importJob.logs.map((line, index) => (
                        <div key={`${index}-${line}`} className="whitespace-pre-wrap">
                          {line}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
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
                          <p className="text-xs text-muted-foreground">
                            Started {run.start_time ? formatDistanceToNow(new Date(run.start_time), { addSuffix: true }) : '—'} • {formatDuration(durationSeconds)}
                          </p>
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
              <li>• Pending HIL reviews? Approve or request follow-up from the dashboard table.</li>
            </ul>
          </div>
        </section>
      </CardContent>
    </Card>
  )
}
