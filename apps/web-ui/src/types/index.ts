// Marquez/OpenLineage API Types

export interface MarquezNamespace {
  name: string
  createdAt: string
  updatedAt: string
  ownerName?: string
  description?: string
}

export interface MarquezJob {
  id: {
    namespace: string
    name: string
  }
  type: string
  name: string
  createdAt: string
  updatedAt: string
  namespace: string
  inputs?: MarquezDataset[]
  outputs?: MarquezDataset[]
  location?: string
  context?: Record<string, unknown>
  description?: string
  latestRun?: MarquezRun
}

export interface MarquezDataset {
  id: {
    namespace: string
    name: string
  }
  type: string
  name: string
  physicalName: string
  createdAt: string
  updatedAt: string
  namespace: string
  sourceName: string
  fields?: MarquezField[]
  tags?: string[]
  description?: string
}

export interface MarquezField {
  name: string
  type: string
  tags?: string[]
  description?: string
}

export interface MarquezRun {
  id: string
  createdAt: string
  updatedAt: string
  nominalStartTime?: string
  nominalEndTime?: string
  state: 'NEW' | 'RUNNING' | 'COMPLETED' | 'ABORTED' | 'FAILED'
  startedAt?: string
  endedAt?: string
  durationMs?: number
  args?: Record<string, unknown>
  context?: Record<string, unknown>
  facets?: Record<string, unknown>
}

export interface MarquezLineageGraphNode {
  id: string
  type: 'DATASET' | 'JOB'
  data: (Partial<MarquezDataset> | Partial<MarquezJob>) & {
    name: string
    namespace: string
  }
  run?: MarquezRun | null
}

export interface MarquezLineageGraphEdge {
  origin: string
  destination: string
}

export interface MarquezLineageGraph {
  graph: {
    nodes: MarquezLineageGraphNode[]
    edges: MarquezLineageGraphEdge[]
  }
  lastUpdatedAt?: string
}

export interface MarquezLineageFilters {
  namespace: string
  name: string
  nodeType: 'JOB' | 'DATASET'
  upstreamDepth?: number
  downstreamDepth?: number
  includeDownstream?: boolean
  includeUpstream?: boolean
  startTime?: string
  endTime?: string
  filterRunStates?: Array<MarquezRun['state']>
}

// Prefect API Types

export interface PrefectFlow {
  id: string
  name: string
  created: string
  updated: string
  tags?: string[]
}

export interface PrefectFlowRun {
  id: string
  name: string
  flow_id: string
  deployment_id?: string
  state_type: 'SCHEDULED' | 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'CRASHED'
  state_name: string
  start_time?: string
  end_time?: string
  expected_start_time?: string
  total_run_time?: number
  created: string
  updated: string
  tags?: string[]
  parameters?: Record<string, unknown>
  hil_status?: 'none' | 'waiting' | 'approved' | 'rejected'
  hil_operator?: string
  hil_timestamp?: string
  hil_comment?: string
}

// Human-in-the-Loop types

export interface HILApproval {
  id: string
  runId: string
  status: 'waiting' | 'approved' | 'rejected'
  operator: string
  timestamp: string
  comment?: string
  reason?: string
}

export interface HILAuditEntry {
  id: string
  runId: string
  action: 'approve' | 'reject' | 'request_review'
  operator: string
  timestamp: string
  comment?: string
  previousStatus?: string
  newStatus: string
}

export interface ActivityEvent {
  id: string
  timestamp: string
  category?: string
  action?: string
  message?: string
  operator?: string
  runId?: string
  jobId?: string
  status?: string
  success?: boolean
  label?: string
  files?: string[]
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

export interface PrefectDeployment {
  id: string
  name: string
  flow_id: string
  created: string
  updated: string
  tags?: string[]
  parameters?: Record<string, unknown>
}

export type PipelineAction =
  | 'refine'
  | 'normalize'
  | 'backfill'
  | 'enrich'
  | 'qa'
  | 'contracts'
  | 'other'

export interface PipelineRun {
  id: string
  source: 'prefect' | 'job'
  action: PipelineAction
  status: 'completed' | 'running' | 'failed' | 'unknown'
  startedAt: string | null
  finishedAt: string | null
  updatedAt: string | null
  profile?: string
  runName?: string
  notes?: string
  dataDocsUrl?: string
  metadata?: Record<string, unknown>
  isRecent?: boolean
}

export interface PipelineRunResponse {
  runs: PipelineRun[]
  lastUpdated?: string
  stats?: {
    totalPrefect?: number
    totalJobs?: number
  }
}

export interface CommandJob {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  label?: string
  command?: string[]
  cwd?: string
  createdAt?: string
  updatedAt?: string
  startedAt?: string
  completedAt?: string
  metadata?: Record<string, unknown>
  exitCode?: number | null
  error?: string | null
}

// Smart import profiling

export type ImportIssueSeverity = 'info' | 'warning' | 'error'

export interface ImportIssue {
  severity: ImportIssueSeverity
  message: string
  code?: string | null
  column?: string | null
}

export interface ImportColumnProfile {
  name: string
  inferredType: string
  confidence: number
  nullFraction: number
  distinctValues: number
  sampleValues: string[]
  issues: ImportIssue[]
}

export interface ImportSheetProfile {
  name: string
  rows: number
  columns: ImportColumnProfile[]
  sampleRows: Array<Record<string, unknown>>
  role: string
  joinKeys: string[]
  issues: ImportIssue[]
}

export interface ImportProfile {
  workbook: string
  sheets: ImportSheetProfile[]
  issues: ImportIssue[]
  generatedAt?: string
}

export interface StoredImportProfile {
  id: string
  createdAt: string
  source: 'upload' | 'filesystem'
  workbookPath?: string
  profile: ImportProfile
  tags?: string[]
  description?: string
}

export interface ImportTemplatePayload {
  import_mappings?: Array<Record<string, unknown>>
  import_rules?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export interface ImportTemplate {
  id: string
  name: string
  description?: string
  profile?: string
  tags?: string[]
  createdAt: string
  updatedAt: string
  payload: ImportTemplatePayload
}

// Hotpass-specific types

export interface HotpassRun {
  id: string
  timestamp: string
  status: 'completed' | 'failed' | 'running' | 'pending'
  duration?: number
  profile: string
  inputPath: string
  outputPath?: string
  qaResults?: QAResult[]
  lineageUrl?: string
  prefectRunId?: string
}

export interface QAResult {
  check: string
  status: 'passed' | 'failed' | 'warning'
  message?: string
  details?: Record<string, unknown>
}

// Configuration types

export interface AppConfig {
  prefectApiUrl: string
  marquezApiUrl: string
  environment: 'local' | 'staging' | 'prod'
}
