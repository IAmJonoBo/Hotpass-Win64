import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'
import compression from 'compression'
import helmet from 'helmet'
import cookieParser from 'cookie-parser'
import csrf from 'csurf'
import rateLimit from 'express-rate-limit'
import { createProxyMiddleware } from 'http-proxy-middleware'
import Busboy from 'busboy'
import os from 'os'
import fs from 'fs'
import { copyFile, mkdir, mkdtemp, readdir, rm, rename, stat, readFile, writeFile } from 'fs/promises'
import crypto from 'crypto'
import { EventEmitter } from 'events'
import { spawn } from 'child_process'
import YAML from 'yaml'
import {
  createCommandJob,
  createJobId,
  getJob,
  listJobs,
  mergeJobMetadata,
  publishJobEvent,
  subscribeToJob,
} from './job-runner.js'
import {
  appendActivityEvent as persistActivityEvent,
  readActivityLog,
  readHilApprovals,
  readHilAudit,
  writeHilApprovals,
  writeHilAudit,
  listImportProfiles,
  readImportProfile,
  writeImportProfile,
  deleteImportProfile,
  listImportTemplates,
  readImportTemplate,
  writeImportTemplate,
  deleteImportTemplate,
} from './storage.js'
import {
  summariseTemplate as summariseTemplateSnapshot,
  summariseConsolidation as summariseConsolidationSnapshot,
  aggregateConsolidationTelemetry,
  buildContractOutput,
} from './template-utils.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export const app = express()

const port = process.env.PORT || 3000
const prefectTarget = process.env.PREFECT_API_URL || process.env.VITE_PREFECT_API_URL || 'http://localhost:4200/api'
const marquezTarget = process.env.MARQUEZ_API_URL || process.env.VITE_MARQUEZ_API_URL || process.env.OPENLINEAGE_URL || 'http://localhost:5000/api/v1'

const prefectLimit = Number.parseInt(process.env.PREFECT_RATE_LIMIT ?? '120', 10)
const marquezLimit = Number.parseInt(process.env.MARQUEZ_RATE_LIMIT ?? '60', 10)
const IMPORT_ROOT = process.env.HOTPASS_IMPORT_ROOT || path.join(process.cwd(), 'dist', 'import')
const CONTRACTS_ROOT = process.env.HOTPASS_CONTRACT_ROOT || path.join(process.cwd(), 'dist', 'contracts')
const MAX_IMPORT_FILE_SIZE = Number.parseInt(process.env.HOTPASS_IMPORT_MAX_FILE_SIZE ?? `${1024 * 1024 * 1024}`, 10)
const MAX_IMPORT_FILES = Number.parseInt(process.env.HOTPASS_IMPORT_MAX_FILES ?? '10', 10)
const PIPELINE_RUN_LIMIT = Number.parseInt(process.env.HOTPASS_PIPELINE_RUN_LIMIT ?? '100', 10)
const INVENTORY_PATH =
  process.env.HOTPASS_INVENTORY_PATH ||
  path.join(process.cwd(), 'data', 'inventory', 'asset-register.yaml')
const INVENTORY_STATUS_PATH =
  process.env.HOTPASS_INVENTORY_FEATURE_STATUS_PATH ||
  path.join(process.cwd(), 'data', 'inventory', 'feature-status.yaml')
const resolveNonNegativeInt = (rawValue, envName, defaultValue) => {
  if (rawValue === undefined || rawValue === null || `${rawValue}`.trim() === '') {
    return defaultValue
  }
  const parsed = Number.parseInt(String(rawValue), 10)
  if (Number.isNaN(parsed) || parsed < 0) {
    throw new Error(`${envName} must be a non-negative integer`)
  }
  return parsed
}

const INVENTORY_CACHE_TTL_SECONDS = resolveNonNegativeInt(
  process.env.HOTPASS_INVENTORY_CACHE_TTL,
  'HOTPASS_INVENTORY_CACHE_TTL',
  300,
)
const INVENTORY_CACHE_TTL_MS = resolveNonNegativeInt(
  process.env.HOTPASS_INVENTORY_CACHE_TTL_MS,
  'HOTPASS_INVENTORY_CACHE_TTL_MS',
  INVENTORY_CACHE_TTL_SECONDS * 1000,
)

const inventoryCache = {
  snapshot: null,
  manifestMtimeMs: 0,
  statusMtimeMs: 0,
  expiresAt: 0,
}

export const resetInventoryCache = () => {
  inventoryCache.snapshot = null
  inventoryCache.manifestMtimeMs = 0
  inventoryCache.statusMtimeMs = 0
  inventoryCache.expiresAt = 0
}

const activityEmitter = new EventEmitter()
activityEmitter.setMaxListeners(0)

const emitActivityEvent = (event) => {
  activityEmitter.emit('event', event)
}

async function appendActivityEvent(event) {
  await persistActivityEvent(event)
  emitActivityEvent(event)
  return event
}

const isRecord = (value) => typeof value === 'object' && value !== null && !Array.isArray(value)

app.disable('x-powered-by')
app.use(helmet({ contentSecurityPolicy: false }))
app.use(compression())
app.use(express.json({ limit: '1mb' }))
app.use(cookieParser())

const csrfProtection = csrf({
  cookie: {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
  },
})

const prefectLimiter = rateLimit({
  windowMs: 60_000,
  max: prefectLimit,
  standardHeaders: true,
  legacyHeaders: false,
  message: 'Prefect API rate limit exceeded',
})

const marquezLimiter = rateLimit({
  windowMs: 60_000,
  max: marquezLimit,
  standardHeaders: true,
  legacyHeaders: false,
  message: 'Marquez API rate limit exceeded',
})

const prefectProxy = createProxyMiddleware({
  target: prefectTarget,
  changeOrigin: true,
  xfwd: true,
  pathRewrite: path => path.replace(/^\/api\/prefect/, ''),
})

const marquezProxy = createProxyMiddleware({
  target: marquezTarget,
  changeOrigin: true,
  xfwd: true,
  pathRewrite: path => path.replace(/^\/api\/marquez/, ''),
})

app.use('/api/prefect', prefectLimiter, prefectProxy)
app.use('/api/marquez', marquezLimiter, marquezProxy)

app.get('/telemetry/operator-feedback/csrf', csrfProtection, (req, res) => {
  res.json({ token: req.csrfToken() })
})

app.post('/telemetry/operator-feedback', csrfProtection, (req, res) => {
  const payload = req.body ?? {}
  if (!payload || typeof payload !== 'object') {
    return res.status(400).json({ error: 'Invalid payload' })
  }

  const { rowId, feedback, metadata } = payload
  if (!rowId || typeof feedback !== 'string') {
    return res.status(422).json({ error: 'rowId and feedback are required' })
  }

  console.log('[telemetry] operator-feedback', {
    rowId,
    feedback,
    metadata,
    receivedAt: new Date().toISOString(),
  })

  res.status(202).json({ status: 'queued' })
})

const sendError = (res, status, message, details) => {
  res.status(status).json({
    error: message,
    ...(details ? { details } : {}),
  })
}

const ensureDirectory = async (dir) => {
  await mkdir(dir, { recursive: true })
}

const moveFile = async (source, destination) => {
  try {
    await rename(source, destination)
  } catch (error) {
    if (error.code === 'EXDEV') {
      await copyFile(source, destination)
      await rm(source, { force: true })
    } else {
      throw error
    }
  }
}

const isImportJob = (job) => Boolean(job?.metadata && job.metadata.type === 'import')

const safeStatFile = async (filePath) => {
  try {
    const stats = await stat(filePath)
    if (stats.isFile()) {
      return stats
    }
    return null
  } catch (error) {
    if (error.code === 'ENOENT') {
      return null
    }
    throw error
  }
}

const parseInventoryArray = value => {
  if (!value) return []
  if (Array.isArray(value)) {
    return [...new Set(value.map(item => String(item)))]
  }
  return [String(value)]
}

const normaliseAssetRecord = raw => {
  if (!isRecord(raw)) return null
  return {
    id: raw.id ? String(raw.id) : raw.name ? String(raw.name) : 'unknown',
    name: raw.name ? String(raw.name) : raw.id ? String(raw.id) : 'unknown',
    type: raw.type ? String(raw.type) : 'unknown',
    location: raw.location ? String(raw.location) : '',
    classification: raw.classification ? String(raw.classification) : 'unknown',
    owner: raw.owner ? String(raw.owner) : 'unknown',
    custodian: raw.custodian ? String(raw.custodian) : '',
    description: raw.description ? String(raw.description) : '',
    dependencies: parseInventoryArray(raw.dependencies),
    controls: parseInventoryArray(raw.controls),
  }
}

const summariseAssets = assets => {
  const byType = new Map()
  const byClassification = new Map()

  for (const asset of assets) {
    byType.set(asset.type, (byType.get(asset.type) ?? 0) + 1)
    byClassification.set(
      asset.classification,
      (byClassification.get(asset.classification) ?? 0) + 1,
    )
  }

  const sortEntries = map => Object.fromEntries([...map.entries()].sort())

  return {
    total: assets.length,
    byType: sortEntries(byType),
    byClassification: sortEntries(byClassification),
  }
}

const parseRequirementPayload = payload => {
  if (!isRecord(payload)) return []
  const rawRequirements = Array.isArray(payload.requirements) ? payload.requirements : []

  const requirements = []
  for (const item of rawRequirements) {
    if (!isRecord(item)) continue
    const status = typeof item.status === 'string' ? item.status : 'planned'
    requirements.push({
      id: item.id ? String(item.id) : 'unknown',
      surface: item.surface ? String(item.surface) : 'unknown',
      description: item.description ? String(item.description) : '',
      status,
      detail: item.detail == null ? null : String(item.detail),
    })
  }
  return requirements
}

const ensureBackendRequirement = (requirements, detail) => {
  let matched = false
  for (const requirement of requirements) {
    const surface = requirement.surface.toLowerCase()
    if (surface === 'backend' || ['backend', 'backend-service'].includes(requirement.id)) {
      requirement.status = 'degraded'
      requirement.detail = detail
      matched = true
      break
    }
  }

  if (!matched) {
    requirements.push({
      id: 'backend',
      surface: 'backend',
      description: 'Inventory manifest is available',
      status: 'degraded',
      detail,
    })
  }
}

const loadInventorySnapshot = async () => {
  const now = Date.now()
  const manifestStats = await safeStatFile(INVENTORY_PATH)
  if (!manifestStats) {
    const error = new Error(`Inventory manifest not found at ${INVENTORY_PATH}`)
    error.code = 'ENOENT'
    throw error
  }

  const statusStats = await safeStatFile(INVENTORY_STATUS_PATH)

  if (
    inventoryCache.snapshot &&
    inventoryCache.manifestMtimeMs === manifestStats.mtimeMs &&
    inventoryCache.statusMtimeMs === (statusStats?.mtimeMs ?? 0) &&
    inventoryCache.expiresAt > now
  ) {
    return inventoryCache.snapshot
  }

  const manifestRaw = await readFile(INVENTORY_PATH, 'utf8')
  const manifestPayload = YAML.parse(manifestRaw) ?? {}
  const rawAssets = Array.isArray(manifestPayload.assets) ? manifestPayload.assets : []
  const assets = rawAssets
    .map(normaliseAssetRecord)
    .filter(Boolean)

  let requirements = []
  if (statusStats) {
    try {
      const statusRaw = await readFile(INVENTORY_STATUS_PATH, 'utf8')
      const statusPayload = YAML.parse(statusRaw) ?? {}
      requirements = parseRequirementPayload(statusPayload)
    } catch (error) {
      console.warn('[inventory] failed to parse feature status file', error)
      requirements = []
    }
  }

  if (!assets.length) {
    ensureBackendRequirement(requirements, 'Inventory manifest contains no assets')
  }

  const manifestVersion = manifestPayload?.version
  const manifestMaintainer = manifestPayload?.maintainer
  const manifestReviewCadence =
    manifestPayload?.review_cadence ?? manifestPayload?.reviewCadence

  const snapshot = {
    manifest: {
      version:
        manifestVersion === undefined || manifestVersion === null
          ? 'unknown'
          : String(manifestVersion),
      maintainer:
        manifestMaintainer === undefined || manifestMaintainer === null
          ? 'unknown'
          : String(manifestMaintainer),
      reviewCadence:
        manifestReviewCadence === undefined || manifestReviewCadence === null
          ? 'unknown'
          : String(manifestReviewCadence),
    },
    summary: summariseAssets(assets),
    requirements,
    assets,
    generatedAt: new Date().toISOString(),
  }

  inventoryCache.snapshot = snapshot
  inventoryCache.manifestMtimeMs = manifestStats.mtimeMs
  inventoryCache.statusMtimeMs = statusStats?.mtimeMs ?? 0
  inventoryCache.expiresAt = now + INVENTORY_CACHE_TTL_MS

  return snapshot
}

const enumerateImportArtifacts = async (job) => {
  if (!isImportJob(job)) {
    return []
  }
  const artifacts = []
  const outputPath = typeof job.metadata.outputPath === 'string' ? job.metadata.outputPath : null
  const archiveDir = typeof job.metadata.archiveDir === 'string' ? job.metadata.archiveDir : null

  if (outputPath) {
    const refinedStats = await safeStatFile(outputPath)
    if (refinedStats) {
      artifacts.push({
        id: 'refined',
        name: path.basename(outputPath),
        kind: 'refined',
        size: refinedStats.size,
        url: `/api/jobs/${job.id}/artifacts/refined`,
      })
    }
  }

  if (archiveDir) {
    try {
      const entries = await readdir(archiveDir)
      for (const entry of entries) {
        const archivePath = path.join(archiveDir, entry)
        const archiveStats = await safeStatFile(archivePath)
        if (!archiveStats) continue
        artifacts.push({
          id: `archive:${entry}`,
          name: entry,
          kind: 'archive',
          size: archiveStats.size,
          url: `/api/jobs/${job.id}/artifacts/archive/${encodeURIComponent(entry)}`,
        })
      }
    } catch (error) {
      if (error.code !== 'ENOENT') {
        console.warn('[import] failed to enumerate archive artifacts', error)
      }
    }
  }

  const profileAttachment = job?.metadata && typeof job.metadata === 'object'
    ? job.metadata.profileAttachment
    : null

  const profilePath = profileAttachment && typeof profileAttachment === 'object' && typeof profileAttachment.path === 'string'
    ? profileAttachment.path
    : null

  if (profilePath) {
    const profileStats = await safeStatFile(profilePath)
    if (profileStats) {
      artifacts.push({
        id: 'profile',
        name: profileAttachment?.name || path.basename(profilePath),
        kind: 'profile',
        size: profileStats.size,
        url: `/api/jobs/${job.id}/artifacts/profile`,
      })
    }
  }

  const contractAttachment = job?.metadata && typeof job.metadata === 'object'
    ? job.metadata.contractAttachment
    : null

  const contractPath = contractAttachment && typeof contractAttachment === 'object' && typeof contractAttachment.path === 'string'
    ? contractAttachment.path
    : null

  if (contractPath) {
    const contractStats = await safeStatFile(contractPath)
    if (contractStats) {
      artifacts.push({
        id: 'contract',
        name: contractAttachment?.name || path.basename(contractPath),
        kind: 'contract',
        size: contractStats.size,
        url: `/api/jobs/${job.id}/artifacts/contract`,
      })
    }
  }

  return artifacts
}

const hilStatusSet = new Set(['waiting', 'approved', 'rejected'])

const createHilApproval = ({ runId, status, operator, comment, reason }) => ({
  id: `hil-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  runId,
  status,
  operator,
  comment: comment ?? undefined,
  reason: reason ?? undefined,
  timestamp: new Date().toISOString(),
})

const createHilAuditEntry = ({ runId, operator, action, comment, previousStatus, newStatus }) => ({
  id: `audit-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  runId,
  operator,
  action,
  comment: comment ?? undefined,
  previousStatus,
  newStatus,
  timestamp: new Date().toISOString(),
})

const parseLimitParam = (value) => {
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') {
    return undefined
  }
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined
}

const mapPrefectState = (state) => {
  const normalised = typeof state === 'string' ? state.toLowerCase() : ''
  switch (normalised) {
    case 'completed':
      return 'completed'
    case 'running':
    case 'pending':
    case 'scheduled':
      return 'running'
    case 'failed':
    case 'crashed':
    case 'cancelled':
      return 'failed'
    default:
      return 'unknown'
  }
}

const derivePipelineAction = ({ name, parameters, tags, metadataType }) => {
  if (metadataType === 'import') {
    return 'refine'
  }
  const loweredName = typeof name === 'string' ? name.toLowerCase() : ''
  const loweredTags = Array.isArray(tags) ? tags.map(tag => String(tag).toLowerCase()) : []
  const parameterAction = typeof parameters?.action === 'string' ? parameters.action.toLowerCase() : null

  const candidates = [
    parameterAction,
    loweredName.includes('enrich') ? 'enrich' : null,
    loweredName.includes('contract') ? 'contracts' : null,
    loweredName.includes('qa') ? 'qa' : null,
    loweredName.includes('normalize') || loweredName.includes('normalise') ? 'normalize' : null,
    loweredName.includes('backfill') ? 'backfill' : null,
    loweredName.includes('refine') ? 'refine' : null,
    loweredTags.find(tag => ['refine', 'enrich', 'qa', 'contracts', 'normalize', 'normalise', 'backfill'].includes(tag)),
  ].filter(Boolean)

  if (candidates.length === 0) {
    return 'other'
  }

  const first = candidates[0]
  if (first === 'normalise') {
    return 'normalize'
  }
  return first
}

const mapPrefectRunToPipeline = (run) => {
  const parameters = (run?.parameters && typeof run.parameters === 'object') ? run.parameters : {}
  const action = derivePipelineAction({
    name: run?.name,
    parameters,
    tags: run?.tags,
  })

  return {
    id: run?.id ?? `prefect-${crypto.randomUUID?.() ?? Date.now()}`,
    source: 'prefect',
    action,
    status: mapPrefectState(run?.state_type),
    startedAt: run?.start_time ?? run?.created ?? null,
    finishedAt: run?.end_time ?? null,
    updatedAt: run?.updated ?? run?.end_time ?? run?.start_time ?? null,
    profile: typeof parameters.profile === 'string' ? parameters.profile : undefined,
    runName: run?.name ?? run?.id ?? undefined,
    notes: typeof parameters.notes === 'string' ? parameters.notes : undefined,
    dataDocsUrl: typeof parameters.data_docs_url === 'string' ? parameters.data_docs_url : undefined,
    metadata: {
      flowId: run?.flow_id ?? null,
      deploymentId: run?.deployment_id ?? null,
      parameters,
      tags: run?.tags ?? [],
      stateName: run?.state_name ?? null,
      hil: {
        status: run?.hil_status ?? null,
        operator: run?.hil_operator ?? null,
        comment: run?.hil_comment ?? null,
        timestamp: run?.hil_timestamp ?? null,
      },
    },
  }
}

const mapJobToPipeline = (job) => {
  const metadata = job?.metadata && typeof job.metadata === 'object' ? job.metadata : {}
  const parameters = metadata.parameters && typeof metadata.parameters === 'object' ? metadata.parameters : {}
  const status = job?.status === 'succeeded'
    ? 'completed'
    : job?.status === 'running'
      ? 'running'
      : job?.status === 'failed'
        ? 'failed'
        : 'unknown'

  const action = derivePipelineAction({
    name: job?.label ?? job?.command?.[0],
    parameters,
    tags: metadata.tags,
    metadataType: metadata.type,
  })

  return {
    id: job?.id ?? `job-${crypto.randomUUID?.() ?? Date.now()}`,
    source: 'job',
    action,
    status,
    startedAt: job?.startedAt ?? job?.createdAt ?? null,
    finishedAt: job?.completedAt ?? null,
    updatedAt: job?.updatedAt ?? job?.completedAt ?? job?.startedAt ?? job?.createdAt ?? null,
    profile: typeof metadata.profile === 'string' ? metadata.profile : undefined,
    runName: job?.label ?? job?.command?.join(' ') ?? undefined,
    notes: typeof metadata.notes === 'string' ? metadata.notes : undefined,
    dataDocsUrl: typeof metadata.dataDocsUrl === 'string' ? metadata.dataDocsUrl : undefined,
    metadata: {
      stage: metadata.stage ?? null,
      artifacts: metadata.artifacts ?? [],
      files: metadata.files ?? [],
      exitCode: job?.exitCode ?? null,
      pid: job?.pid ?? null,
      cwd: job?.cwd ?? null,
    },
  }
}

const fetchRecentPrefectRuns = async (limit) => {
  const resolvedLimit = Number.isFinite(limit) && limit > 0 ? Math.min(limit, PIPELINE_RUN_LIMIT) : 50
  const base = prefectTarget.endsWith('/') ? prefectTarget.slice(0, -1) : prefectTarget
  const url = `${base}/flow_runs/filter`

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        limit: resolvedLimit,
        sort: 'START_TIME_DESC',
      }),
    })
    if (!response.ok) {
      console.warn('[pipeline-runs] Prefect returned non-200 response', response.status)
      return []
    }
    const payload = await response.json()
    if (Array.isArray(payload?.result)) {
      return payload.result
    }
    if (Array.isArray(payload?.flow_runs)) {
      return payload.flow_runs
    }
    if (Array.isArray(payload)) {
      return payload
    }
    return []
  } catch (error) {
    console.error('[pipeline-runs] Failed to fetch Prefect runs', error)
    return []
  }
}

const normaliseActionFilter = (input) => {
  if (!input) return null
  const values = Array.isArray(input) ? input : String(input).split(',')
  const cleaned = values
    .map(value => String(value).trim().toLowerCase())
    .filter(Boolean)
  return cleaned.length > 0 ? new Set(cleaned) : null
}

const extractJsonPayload = (raw) => {
  const start = raw.indexOf('{')
  const end = raw.lastIndexOf('}')
  if (start === -1 || end === -1 || end < start) {
    throw new Error('Profiler did not return valid JSON output')
  }
  const snippet = raw.slice(start, end + 1)
  return JSON.parse(snippet)
}

const runImportProfiler = (workbookPath, { sampleRows, maxRows }) =>
  new Promise((resolve, reject) => {
    const args = ['run', 'hotpass', 'imports', 'profile', '--workbook', workbookPath]
    if (Number.isFinite(sampleRows) && sampleRows > 0) {
      args.push('--sample-rows', String(sampleRows))
    }
    if (Number.isFinite(maxRows) && maxRows > 0) {
      args.push('--max-rows', String(maxRows))
    }

    const child = spawn('uv', args, {
      cwd: process.cwd(),
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString()
    })

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString()
    })

    child.on('error', (error) => {
      reject(new Error(`Profiler failed to start: ${error.message}`))
    })

    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `Profiler exited with code ${code}`))
        return
      }
      try {
        resolve(extractJsonPayload(stdout))
      } catch (error) {
        reject(new Error(`Failed to parse profiler output: ${error.message}`))
      }
    })
  })

app.post('/api/imports/profile', async (req, res) => {
  const parseInteger = (value, fallback) => {
    if (value === undefined || value === null) return fallback
    const parsed = Number.parseInt(Array.isArray(value) ? value[0] : value, 10)
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return fallback
    }
    return parsed
  }

  const sampleRows = parseInteger(req.query.sampleRows, 5)
  const maxRows = req.query.maxRows !== undefined ? parseInteger(req.query.maxRows, undefined) : undefined

  const profileAndRespond = async (workbookPath) => {
    try {
      const stats = await stat(workbookPath)
      if (!stats.isFile()) {
        return sendError(res, 400, 'Workbook must be a file')
      }
      const profile = await runImportProfiler(workbookPath, { sampleRows, maxRows })
      res.json({ profile })
    } catch (error) {
      console.error('[imports] profiling failed', error)
      if (error.code === 'ENOENT') {
        sendError(res, 404, 'Workbook not found')
      } else {
        sendError(res, 500, 'Failed to profile workbook', { message: error.message })
      }
    }
  }

  if (req.is('application/json')) {
    const workbookPath = req.body?.workbookPath
    if (!workbookPath || typeof workbookPath !== 'string') {
      return sendError(res, 400, 'workbookPath is required in JSON payload')
    }
    const resolved = path.resolve(process.cwd(), workbookPath)
    if (!resolved.startsWith(process.cwd())) {
      return sendError(res, 400, 'workbookPath must be within the project directory')
    }
    return profileAndRespond(resolved)
  }

  const contentType = req.headers['content-type'] ?? ''
  if (!contentType.includes('multipart/form-data')) {
    return sendError(res, 415, 'Unsupported content type. Use multipart/form-data or JSON.')
  }

  let tempDir
  try {
    tempDir = await mkdtemp(path.join(os.tmpdir(), 'hotpass-profile-'))
  } catch (error) {
    console.error('[imports] failed to allocate temp directory', error)
    return sendError(res, 500, 'Unable to initialise upload workspace', { message: error.message })
  }

  let uploadedPath = null
  let streamError = null

  const busboy = Busboy({ headers: req.headers })

  busboy.on('file', (_fieldname, file, filename) => {
    if (uploadedPath) {
      file.resume()
      return
    }
    const safeName = path.basename(filename || 'workbook.xlsx')
    uploadedPath = path.join(tempDir, safeName)
    const writeStream = fs.createWriteStream(uploadedPath)
    writeStream.on('error', (error) => {
      streamError = error
      file.resume()
    })
    file.pipe(writeStream)
  })

  busboy.on('error', (error) => {
    streamError = error
  })

  busboy.on('finish', async () => {
    try {
      if (streamError) {
        console.error('[imports] upload failed', streamError)
        sendError(res, 400, 'Failed to receive workbook', { message: streamError.message })
        return
      }
      if (!uploadedPath) {
        sendError(res, 400, 'No workbook file was uploaded')
        return
      }
      await profileAndRespond(uploadedPath)
    } finally {
      await rm(tempDir, { recursive: true, force: true }).catch(() => {})
    }
  })

  req.pipe(busboy)
})

app.get('/api/imports/profiles', async (_req, res) => {
  try {
    const profiles = await listImportProfiles()
    res.json({ profiles })
  } catch (error) {
    console.error('[imports] failed to list profiles', error)
    sendError(res, 500, 'Unable to load stored profiles', { message: error.message })
  }
})

app.get('/api/imports/profiles/:id', async (req, res) => {
  const { id } = req.params
  try {
    const profile = await readImportProfile(id)
    if (!profile) {
      return sendError(res, 404, 'Profile not found')
    }
    res.json(profile)
  } catch (error) {
    console.error('[imports] failed to read profile', error)
    sendError(res, 500, 'Unable to load stored profile', { message: error.message })
  }
})

app.post('/api/imports/profiles', csrfProtection, async (req, res) => {
  if (!isRecord(req.body) || !isRecord(req.body.profile)) {
    return sendError(res, 400, 'profile payload is required')
  }
  const entry = {
    id: typeof req.body.id === 'string' ? req.body.id : undefined,
    profile: req.body.profile,
    source: typeof req.body.source === 'string' ? req.body.source : 'upload',
    workbookPath: typeof req.body.workbookPath === 'string' ? req.body.workbookPath : undefined,
    description: typeof req.body.description === 'string' ? req.body.description : undefined,
    tags: Array.isArray(req.body.tags) ? req.body.tags : undefined,
  }
  try {
    const stored = await writeImportProfile(entry)
    res.status(201).json(stored)
  } catch (error) {
    console.error('[imports] failed to persist profile', error)
    sendError(res, 500, 'Unable to persist profile', { message: error.message })
  }
})

app.delete('/api/imports/profiles/:id', csrfProtection, async (req, res) => {
  const { id } = req.params
  try {
    const deleted = await deleteImportProfile(id)
    if (!deleted) {
      return sendError(res, 404, 'Profile not found')
    }
    res.status(204).send()
  } catch (error) {
    console.error('[imports] failed to delete profile', error)
    sendError(res, 500, 'Unable to delete profile', { message: error.message })
  }
})

app.get('/api/imports/templates', async (_req, res) => {
  try {
    const templates = await listImportTemplates()
    res.json({ templates })
  } catch (error) {
    console.error('[imports] failed to list templates', error)
    sendError(res, 500, 'Unable to load templates', { message: error.message })
  }
})

app.get('/api/imports/consolidation/telemetry', async (_req, res) => {
  try {
    const templates = await listImportTemplates()
    const enrichedTemplates = await Promise.all(templates.map(async (template) => {
      const fullTemplate = await readImportTemplate(template.id)
      return {
        ...template,
        payload: fullTemplate?.payload ?? template.payload ?? {},
      }
    }))
    const aggregate = aggregateConsolidationTelemetry(enrichedTemplates)
    const summaries = enrichedTemplates.map(template => ({
      id: template.id,
      name: template.name,
      summary: summariseTemplateSnapshot(template, template.payload),
      consolidation: summariseConsolidationSnapshot(template.payload),
    }))
    res.json({
      aggregate,
      templates: summaries,
    })
  } catch (error) {
    console.error('[imports] failed to build consolidation telemetry', error)
    sendError(res, 500, 'Unable to load consolidation telemetry', { message: error.message })
  }
})

app.get('/api/imports/templates/:id', async (req, res) => {
  const { id } = req.params
  try {
    const template = await readImportTemplate(id)
    if (!template) {
      return sendError(res, 404, 'Template not found')
    }
    res.json(template)
  } catch (error) {
    console.error('[imports] failed to read template', error)
    sendError(res, 500, 'Unable to load template', { message: error.message })
  }
})

app.get('/api/imports/templates/:id/summary', async (req, res) => {
  const { id } = req.params
  try {
    const template = await readImportTemplate(id)
    if (!template) {
      return sendError(res, 404, 'Template not found')
    }
    const summary = summariseTemplateSnapshot(template, template.payload)
    const consolidation = summariseConsolidationSnapshot(template.payload)
    res.json({ template, summary, consolidation })
  } catch (error) {
    console.error('[imports] failed to summarise template', error)
    sendError(res, 500, 'Unable to summarise template', { message: error.message })
  }
})

app.get('/api/inventory', async (_req, res) => {
  try {
    const snapshot = await loadInventorySnapshot()
    res.json(snapshot)
  } catch (error) {
    console.error('[inventory] failed to load inventory', error)
    const message = error instanceof Error ? error.message : 'Unknown inventory error'
    if (error?.code === 'ENOENT') {
      sendError(res, 503, 'Inventory manifest not found', { message })
    } else {
      sendError(res, 500, 'Unable to load inventory', { message })
    }
  }
})

const listContracts = async () => {
  await ensureDirectory(CONTRACTS_ROOT)
  const entries = await readdir(CONTRACTS_ROOT, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    if (!entry.isFile()) continue
    const name = entry.name
    const ext = path.extname(name).toLowerCase()
    if (!['.yaml', '.yml', '.json'].includes(ext)) continue
    const filePath = path.join(CONTRACTS_ROOT, name)
    try {
      const stats = await stat(filePath)
      files.push({
        id: `${name}-${stats.mtimeMs}`,
        name,
        format: ext.replace('.', ''),
        profile: path.basename(name, ext),
        size: stats.size,
        updatedAt: stats.mtime.toISOString(),
      })
    } catch (error) {
      console.warn('[contracts] failed to stat file', { name, error })
    }
  }
  files.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
  return files
}

app.get('/api/contracts', async (_req, res) => {
  try {
    const contracts = await listContracts()
    const payload = contracts.map(contract => ({
      ...contract,
      downloadUrl: `/api/contracts/${encodeURIComponent(contract.name)}/download`,
    }))
    res.json({ contracts: payload })
  } catch (error) {
    console.error('[contracts] failed to list contracts', error)
    sendError(res, 500, 'Unable to load contracts', { message: error.message })
  }
})

app.get('/api/contracts/:name/download', async (req, res) => {
  const safeName = path.basename(req.params.name)
  if (!safeName) {
    return sendError(res, 400, 'Invalid contract name')
  }
  const filePath = path.join(CONTRACTS_ROOT, safeName)
  try {
    const stats = await stat(filePath)
    if (!stats.isFile()) {
      return sendError(res, 404, 'Contract file not found')
    }
    res.download(filePath, safeName)
  } catch (error) {
    if (error.code === 'ENOENT') {
      sendError(res, 404, 'Contract file not found')
    } else {
      console.error('[contracts] failed to download contract', error)
      sendError(res, 500, 'Unable to download contract', { message: error.message })
    }
  }
})

const normaliseTemplatePayload = (payload) => {
  if (!isRecord(payload)) {
    throw new Error('Template payload must be an object')
  }
  return payload
}

app.post('/api/imports/templates', csrfProtection, async (req, res) => {
  if (!isRecord(req.body)) {
    return sendError(res, 400, 'Template body must be an object')
  }
  try {
    const stored = await writeImportTemplate({
      id: typeof req.body.id === 'string' ? req.body.id : undefined,
      name: req.body.name,
      description: typeof req.body.description === 'string' ? req.body.description : undefined,
      profile: typeof req.body.profile === 'string' ? req.body.profile : undefined,
      tags: Array.isArray(req.body.tags) ? req.body.tags : undefined,
      payload: normaliseTemplatePayload(req.body.payload),
    })
    res.status(201).json(stored)
  } catch (error) {
    console.error('[imports] failed to persist template', error)
    if (error.message === 'Template name is required' || error.message === 'Template payload must be an object') {
      sendError(res, 422, error.message)
    } else {
      sendError(res, 500, 'Unable to persist template', { message: error.message })
    }
  }
})

app.put('/api/imports/templates/:id', csrfProtection, async (req, res) => {
  if (!isRecord(req.body)) {
    return sendError(res, 400, 'Template body must be an object')
  }
  const { id } = req.params
  try {
    const stored = await writeImportTemplate({
      id,
      name: req.body.name,
      description: typeof req.body.description === 'string' ? req.body.description : undefined,
      profile: typeof req.body.profile === 'string' ? req.body.profile : undefined,
      tags: Array.isArray(req.body.tags) ? req.body.tags : undefined,
      payload: normaliseTemplatePayload(req.body.payload),
    })
    res.json(stored)
  } catch (error) {
    console.error('[imports] failed to update template', error)
    if (error.message === 'Template name is required' || error.message === 'Template payload must be an object') {
      sendError(res, 422, error.message)
    } else {
      sendError(res, 500, 'Unable to update template', { message: error.message })
    }
  }
})

app.delete('/api/imports/templates/:id', csrfProtection, async (req, res) => {
  const { id } = req.params
  try {
    const deleted = await deleteImportTemplate(id)
    if (!deleted) {
      return sendError(res, 404, 'Template not found')
    }
    res.status(204).send()
  } catch (error) {
    console.error('[imports] failed to delete template', error)
    sendError(res, 500, 'Unable to delete template', { message: error.message })
  }
})

app.post('/api/imports/templates/:id/contracts', csrfProtection, async (req, res) => {
  const { id } = req.params
  const formatRaw = typeof req.body?.format === 'string' ? req.body.format.toLowerCase().trim() : 'yaml'
  const format = ['yaml', 'json'].includes(formatRaw) ? formatRaw : 'yaml'
  try {
    const template = await readImportTemplate(id)
    if (!template) {
      return sendError(res, 404, 'Template not found')
    }
    const contractsDir = path.join(process.cwd(), 'dist', 'contracts')
    await ensureDirectory(contractsDir)
    const { profile, outputPath, filename } = buildContractOutput({ template, outputDir: contractsDir, format })
    const command = [
      'uv',
      'run',
      'hotpass',
      'contracts',
      'emit',
      '--profile',
      profile,
      '--format',
      format,
      '--output',
      outputPath,
    ]
    const job = createCommandJob({
      command,
      label: `Contract (${template.name ?? profile})`,
      metadata: {
        type: 'contract',
        templateId: id,
        templateName: template.name ?? id,
        profile,
        format,
        outputPath,
        contractAttachment: {
          path: outputPath,
          name: filename,
          format,
        },
      },
    })
    mergeJobMetadata(job.id, {
      stage: 'queued',
      type: 'contract',
      templateId: id,
      profile,
      format,
    })

    const unsubscribe = subscribeToJob(job.id, (payload) => {
      if (payload.type === 'finished') {
        ;(async () => {
          try {
            const stats = await safeStatFile(outputPath)
            if (stats) {
              mergeJobMetadata(job.id, {
                contractAttachment: {
                  path: outputPath,
                  name: filename,
                  format,
                },
                artifacts: [
                  {
                    id: 'contract',
                    name: filename,
                    kind: 'contract',
                    size: stats.size,
                    url: `/api/jobs/${job.id}/artifacts/contract`,
                  },
                ],
              })
              publishJobEvent(job.id, {
                type: 'artifact-ready',
                artifacts: [
                  {
                    id: 'contract',
                    name: filename,
                    kind: 'contract',
                    size: stats.size,
                    url: `/api/jobs/${job.id}/artifacts/contract`,
                  },
                ],
                timestamp: new Date().toISOString(),
              })
            }
          } catch (error) {
            console.error('[contracts] failed to finalise contract job', error)
          } finally {
            unsubscribe()
          }
        })().catch((error) => {
          console.error('[contracts] post-processing error', error)
          unsubscribe()
        })
      }
    })

    res.status(201).json({ job })
  } catch (error) {
    console.error('[contracts] failed to publish contract', error)
    sendError(res, 500, 'Unable to publish contract', { message: error.message })
  }
})

app.post('/api/commands/run', csrfProtection, (req, res) => {
  const payload = req.body ?? {}
  const command = payload.command
  if (!Array.isArray(command) || command.length === 0 || !command.every(item => typeof item === 'string' && item.trim().length > 0)) {
    return sendError(res, 400, 'Command must be a non-empty array of strings')
  }

  const label = typeof payload.label === 'string' && payload.label.trim().length > 0 ? payload.label.trim() : undefined
  const cwd = typeof payload.cwd === 'string' && payload.cwd.trim().length > 0 ? payload.cwd.trim() : undefined
  const env = payload.env && typeof payload.env === 'object' ? payload.env : undefined
  const metadata = payload.metadata && typeof payload.metadata === 'object' ? payload.metadata : undefined

  try {
    const job = createCommandJob({
      command,
      cwd,
      env,
      metadata,
      label,
    })
    res.status(201).json({ job })
  } catch (error) {
    console.error('[command-job] failed to start command', error)
    sendError(res, 500, 'Failed to start command', { message: error.message })
  }
})

app.post('/api/import', csrfProtection, async (req, res) => {
  let tempDir
  try {
    tempDir = await mkdtemp(path.join(os.tmpdir(), 'hotpass-import-'))
  } catch (error) {
    console.error('[import] failed to create temp directory', error)
    return sendError(res, 500, 'Unable to initialise upload workspace', { message: error.message })
  }

  const uploadedFiles = []
  const filePromises = []
  const fields = {}
  let fileLimitExceeded = false
  let streamError = null

  const busboy = Busboy({
    headers: req.headers,
    limits: {
      files: MAX_IMPORT_FILES,
      fileSize: MAX_IMPORT_FILE_SIZE,
    },
  })

  busboy.on('file', (fieldname, file, filename, encoding, mimetype) => {
    if (!filename) {
      file.resume()
      return
    }

    const safeName = path.basename(filename).replace(/\0/g, '')
    const destination = path.join(tempDir, safeName)
    const writeStream = fs.createWriteStream(destination)
    let size = 0

    file.on('data', (chunk) => {
      size += chunk.length
    })

    const writePromise = new Promise((resolve, reject) => {
      file.on('limit', () => {
        fileLimitExceeded = true
        writeStream.destroy()
        reject(new Error('File exceeded allowed size'))
      })
      file.on('error', reject)
      writeStream.on('error', reject)
      writeStream.on('finish', () => resolve({
        fieldname,
        originalName: filename,
        filename: safeName,
        path: destination,
        mimetype,
        encoding,
        size,
      }))
    })

    file.pipe(writeStream)
    filePromises.push(writePromise)
  })

  busboy.on('field', (name, value) => {
    fields[name] = value
  })

  busboy.on('error', (error) => {
    streamError = error
  })

  const finishedParsing = new Promise((resolve, reject) => {
    busboy.on('finish', resolve)
    busboy.on('error', reject)
  })

  req.pipe(busboy)

  try {
    await finishedParsing
    uploadedFiles.push(...await Promise.all(filePromises))
  } catch (error) {
    streamError = streamError ?? error
  }

  if (fileLimitExceeded) {
    await rm(tempDir, { recursive: true, force: true })
    return sendError(res, 413, 'One or more files exceed the allowed size limit', { maxBytes: MAX_IMPORT_FILE_SIZE })
  }

  if (streamError) {
    console.error('[import] upload stream failed', streamError)
    await rm(tempDir, { recursive: true, force: true })
    return sendError(res, 400, 'Failed to receive files', { message: streamError.message })
  }

  if (uploadedFiles.length === 0) {
    await rm(tempDir, { recursive: true, force: true })
    return sendError(res, 400, 'No files were uploaded')
  }

  const parseBooleanField = (value) => {
    if (typeof value === 'boolean') return value
    if (typeof value === 'string') {
      const normalised = value.trim().toLowerCase()
      if (['true', '1', 'yes', 'on'].includes(normalised)) return true
      if (['false', '0', 'no', 'off'].includes(normalised)) return false
    }
    return false
  }

  const attachProfile = parseBooleanField(fields.attachProfile)
  let profilePayload = null
  if (attachProfile) {
    const rawPayload = typeof fields.profilePayload === 'string' ? fields.profilePayload.trim() : ''
    if (!rawPayload) {
      await rm(tempDir, { recursive: true, force: true })
      return sendError(res, 400, 'profilePayload is required when attachProfile is true')
    }
    try {
      profilePayload = JSON.parse(rawPayload)
    } catch (error) {
      await rm(tempDir, { recursive: true, force: true })
      return sendError(res, 400, 'profilePayload must be valid JSON', { message: error.message })
    }
  }

  const profileSourceName = typeof fields.profileSourceName === 'string' && fields.profileSourceName.trim().length > 0
    ? fields.profileSourceName.trim()
    : undefined

  const profile = typeof fields.profile === 'string' && fields.profile.trim().length > 0
    ? fields.profile.trim()
    : 'generic'
  const notes = typeof fields.notes === 'string' && fields.notes.trim().length > 0
    ? fields.notes.trim()
    : undefined

  const jobId = createJobId()
  const jobRoot = path.join(IMPORT_ROOT, jobId)
  const inputDir = path.join(jobRoot, 'input')
  const outputPath = path.join(jobRoot, 'refined.xlsx')
  const archiveDir = path.join(jobRoot, 'archives')

  const filesMetadata = []
  let jobLabel = ''

  try {
    await ensureDirectory(inputDir)
    await ensureDirectory(archiveDir)
    for (const uploaded of uploadedFiles) {
      const destination = path.join(inputDir, uploaded.filename)
      await ensureDirectory(path.dirname(destination))
      await moveFile(uploaded.path, destination)
      const fileStats = await stat(destination)
      filesMetadata.push({
        originalName: uploaded.originalName,
        filename: uploaded.filename,
        size: fileStats.size,
        mimetype: uploaded.mimetype,
      })
    }

    await rm(tempDir, { recursive: true, force: true })

    let profileAttachmentMeta = null
    if (attachProfile && profilePayload) {
      const deriveProfileFilename = (sourceName) => {
        if (!sourceName) return 'profile.json'
        const base = sourceName
          .replace(/\.[^/.]+$/, '')
          .replace(/[^a-z0-9-_]+/gi, '_')
          .replace(/_{2,}/g, '_')
          .replace(/^_+|_+$/g, '')
          .slice(0, 64)
        return base ? `${base}-profile.json` : 'profile.json'
      }

      const referenceName =
        profileSourceName ||
        filesMetadata[0]?.originalName ||
        uploadedFiles[0]?.originalName ||
        'workbook'
      const profileFilename = deriveProfileFilename(referenceName)
      const profilePath = path.join(jobRoot, profileFilename)
      const payloadToPersist = {
        ...profilePayload,
      }
      if (typeof payloadToPersist.attachedAt !== 'string') {
        payloadToPersist.attachedAt = new Date().toISOString()
      }

      await writeFile(profilePath, `${JSON.stringify(payloadToPersist, null, 2)}\n`, 'utf8')
      const profileStats = await stat(profilePath)
      profileAttachmentMeta = {
        path: profilePath,
        name: profileFilename,
        sourceName: referenceName,
        size: profileStats.size,
        attachedAt: payloadToPersist.attachedAt,
      }

      try {
        const storedProfile = await writeImportProfile({
          id: jobId,
          profile: payloadToPersist,
          source: 'upload',
          workbookPath: referenceName,
          tags: [profile],
          description: `Attached during import ${jobId}`,
        })
        if (storedProfile?.id) {
          profileAttachmentMeta.profileId = storedProfile.id
        }
      } catch (error) {
        console.warn('[import] failed to persist profile snapshot', error)
      }
    }

    const command = [
      'uv',
      'run',
      'hotpass',
      'refine',
      '--input-dir',
      inputDir,
      '--output-path',
      outputPath,
      '--profile',
      profile,
      '--archive',
      '--dist-dir',
      archiveDir,
    ]

    jobLabel = filesMetadata.length === 1
      ? `Import ${filesMetadata[0].originalName}`
      : `Import ${filesMetadata.length} files`

    const metadata = {
      type: 'import',
      profile,
      inputDir,
      outputPath,
      archiveDir,
      files: filesMetadata,
      ...(notes ? { notes } : {}),
      ...(profileAttachmentMeta ? {
        profileAttachment: {
          path: profileAttachmentMeta.path,
          name: profileAttachmentMeta.name,
          sourceName: profileAttachmentMeta.sourceName,
          size: profileAttachmentMeta.size,
          attachedAt: profileAttachmentMeta.attachedAt,
        },
        artifacts: [
          {
            id: 'profile',
            name: profileAttachmentMeta.name,
            kind: 'profile',
            size: profileAttachmentMeta.size,
            url: `/api/jobs/${jobId}/artifacts/profile`,
          },
        ],
      } : {}),
    }

    const job = createCommandJob({
      command,
      metadata,
      label: jobLabel,
      requestedId: jobId,
    })

    mergeJobMetadata(job.id, {
      stage: 'queued',
      profile,
      files: filesMetadata,
      ...(notes ? { notes } : {}),
      ...(profileAttachmentMeta ? {
        profileAttachment: metadata.profileAttachment,
        artifacts: metadata.artifacts,
      } : {}),
    })

    await appendActivityEvent(createActivityEvent({
      category: 'import',
      action: 'queued',
      jobId: job.id,
      label: jobLabel,
      profile,
      files: filesMetadata.map(file => file.originalName),
      success: true,
    }))

    for (const fileMeta of filesMetadata) {
      publishJobEvent(job.id, {
        type: 'file-accepted',
        file: fileMeta,
        timestamp: new Date().toISOString(),
      })
    }

    if (profileAttachmentMeta) {
      publishJobEvent(job.id, {
        type: 'artifact-ready',
        artifacts: metadata.artifacts,
        timestamp: new Date().toISOString(),
      })
    }

    publishJobEvent(job.id, {
      type: 'stage',
      stage: 'upload-complete',
      timestamp: new Date().toISOString(),
    })

    void appendActivityEvent(createActivityEvent({
      category: 'import',
      action: 'upload-complete',
      jobId: job.id,
      label: jobLabel,
      profile,
      files: filesMetadata.map(file => file.originalName),
      success: true,
    })).catch(() => {})

    const unsubscribe = subscribeToJob(job.id, (payload) => {
      if (payload.type === 'started') {
        publishJobEvent(job.id, {
          type: 'stage',
          stage: 'refine-started',
          timestamp: new Date().toISOString(),
        })
        void appendActivityEvent(createActivityEvent({
          category: 'import',
          action: 'refine-started',
          jobId: job.id,
          label: jobLabel,
          profile,
          success: true,
        })).catch(() => {})
      }
      if (payload.type === 'finished') {
        (async () => {
          try {
            const artifacts = await enumerateImportArtifacts(job)
            if (artifacts.length > 0) {
              mergeJobMetadata(job.id, { artifacts })
              publishJobEvent(job.id, {
                type: 'artifact-ready',
                artifacts,
                timestamp: new Date().toISOString(),
              })
            }
            const status = typeof payload?.status === 'string' ? payload.status : job.status
            const completed = status === 'succeeded'
            await appendActivityEvent(createActivityEvent({
              category: 'import',
              action: completed ? 'completed' : 'failed',
              jobId: job.id,
              label: jobLabel,
              profile,
              success: completed,
              status,
              artifacts,
              error: completed ? undefined : payload?.error ?? job.error ?? null,
            }))
          } finally {
            unsubscribe()
          }
        })().catch((error) => {
          console.error('[import] failed to enumerate artifacts', error)
          unsubscribe()
        })
      }
      if (payload.type === 'error') {
        void appendActivityEvent(createActivityEvent({
          category: 'import',
          action: 'errored',
          jobId: job.id,
          label: jobLabel,
          profile,
          success: false,
          status: 'failed',
          error: payload?.error ?? 'unknown',
        })).catch(() => {})
        unsubscribe()
      }
    })

    res.status(202).json({ job })
  } catch (error) {
    console.error('[import] failed to dispatch refine job', error)
    await rm(jobRoot, { recursive: true, force: true }).catch(() => {})
    await rm(tempDir, { recursive: true, force: true }).catch(() => {})
    await appendActivityEvent(createActivityEvent({
      category: 'import',
      action: 'failed-to-start',
      label: jobLabel,
      profile,
      success: false,
      files: filesMetadata.map(file => file.originalName),
      error: error instanceof Error ? error.message : String(error),
    })).catch(() => {})
    sendError(res, 500, 'Failed to start import job', { message: error.message })
  }
})

app.get('/api/jobs', (req, res) => {
  res.json({ jobs: listJobs() })
})

app.get('/api/jobs/:id', (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  res.json({ job })
})

app.get('/api/jobs/:id/events', (req, res) => {
  const { id } = req.params
  const job = getJob(id)
  if (!job) {
    res.writeHead(404, {
      'Content-Type': 'application/json',
    })
    res.end(JSON.stringify({ error: 'Job not found' }))
    return
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  })

  const sendEvent = (event, data) => {
    res.write(`event: ${event}\n`)
    res.write(`data: ${JSON.stringify(data)}\n\n`)
  }

  sendEvent('snapshot', { job })

  const unsubscribe = subscribeToJob(id, (payload) => {
    sendEvent(payload.type ?? 'update', payload)
  })

  const keepAlive = setInterval(() => {
    res.write(': keep-alive\n\n')
  }, 25_000)

  req.on('close', () => {
    clearInterval(keepAlive)
    unsubscribe()
  })
})

app.get('/api/runs/:id/logs', (req, res) => {
  const { id } = req.params
  const job = getJob(id)
  if (!job) {
    return sendError(res, 404, 'Logs unavailable for this run')
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  })

  const sendEvent = (event, data) => {
    res.write(`event: ${event}\n`)
    res.write(`data: ${JSON.stringify(data)}\n\n`)
  }

  const snapshotLogs = Array.isArray(job.log)
    ? job.log.map((entry) => ({
        message: entry.message ?? '',
        stream: entry.type ?? 'stdout',
        timestamp: entry.timestamp ?? new Date().toISOString(),
      }))
    : []

  sendEvent('snapshot', { logs: snapshotLogs })

  const unsubscribe = subscribeToJob(id, (payload) => {
    if (!payload || typeof payload !== 'object') return
    if (payload.type === 'log' && typeof payload.message === 'string') {
      sendEvent('log', {
        message: payload.message,
        stream: payload.stream ?? 'stdout',
        timestamp: new Date().toISOString(),
      })
    }
    if (payload.type === 'finished') {
      sendEvent('finished', { status: payload.status ?? job.status ?? 'unknown' })
    }
  })

  const keepAlive = setInterval(() => {
    res.write(': keep-alive\n\n')
  }, 25_000)

  req.on('close', () => {
    clearInterval(keepAlive)
    unsubscribe()
  })
})

app.get('/api/runs/recent', async (req, res) => {
  const limit = parseLimitParam(req.query.limit) ?? 50
  const actionsFilter = normaliseActionFilter(req.query.action)
  const includeJobs = req.query.includeJobs !== 'false'
  const includePrefect = req.query.includePrefect !== 'false'

  try {
    const tasks = []
    if (includePrefect) {
      tasks.push(fetchRecentPrefectRuns(limit))
    } else {
      tasks.push(Promise.resolve([]))
    }
    if (includeJobs) {
      tasks.push(Promise.resolve(listJobs()))
    } else {
      tasks.push(Promise.resolve([]))
    }

    const [prefectRunsRaw, jobsRaw] = await Promise.all(tasks)
    const prefectRuns = Array.isArray(prefectRunsRaw) ? prefectRunsRaw.map(mapPrefectRunToPipeline) : []
    const jobRuns = Array.isArray(jobsRaw) ? jobsRaw.map(mapJobToPipeline) : []

    const combined = [...prefectRuns, ...jobRuns]
      .filter((run) => {
        if (!actionsFilter) return true
        return actionsFilter.has(String(run.action ?? '').toLowerCase())
      })
      .map((run) => {
        const updatedAt = run.updatedAt ? new Date(run.updatedAt).toISOString() : null
        const updatedMs = updatedAt ? new Date(updatedAt).getTime() : null
        const isRecent = typeof updatedMs === 'number' && !Number.isNaN(updatedMs) && (Date.now() - updatedMs) <= 2_000
        return {
          ...run,
          updatedAt,
          isRecent,
        }
      })
      .sort((a, b) => {
        const timeA = a.updatedAt ? new Date(a.updatedAt).getTime() : 0
        const timeB = b.updatedAt ? new Date(b.updatedAt).getTime() : 0
        return timeB - timeA
      })
      .slice(0, Math.min(limit, PIPELINE_RUN_LIMIT))

    res.json({
      runs: combined,
      lastUpdated: new Date().toISOString(),
      stats: {
        totalPrefect: prefectRuns.length,
        totalJobs: jobRuns.length,
      },
    })
  } catch (error) {
    console.error('[pipeline-runs] failed to build response', error)
    sendError(res, 500, 'Failed to load recent runs', { message: error.message })
  }
})

app.get('/api/hil/approvals', async (_req, res) => {
  try {
    const approvals = await readHilApprovals()
    res.json({ approvals })
  } catch (error) {
    console.error('[hil] failed to read approvals', error)
    sendError(res, 500, 'Failed to read approvals', { message: error.message })
  }
})

app.get('/api/hil/audit', async (req, res) => {
  try {
    const limit = parseLimitParam(req.query.limit)
    const entries = await readHilAudit()
    const slice = limit ? entries.slice(0, limit) : entries
    res.json({ entries: slice })
  } catch (error) {
    console.error('[hil] failed to read audit log', error)
    sendError(res, 500, 'Failed to read audit log', { message: error.message })
  }
})

const createActivityEvent = (payload) => ({
  id: `activity-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
  timestamp: new Date().toISOString(),
  category: payload.category ?? payload.type ?? 'general',
  ...payload,
})

app.get('/api/activity', async (req, res) => {
  try {
    const limit = parseLimitParam(req.query.limit)
    const events = await readActivityLog()
    const slice = limit ? events.slice(0, limit) : events
    res.json({ events: slice })
  } catch (error) {
    console.error('[activity] failed to read log', error)
    sendError(res, 500, 'Failed to read activity log', { message: error.message })
  }
})

app.get('/api/activity/events', async (req, res) => {
  const limit = parseLimitParam(req.query.limit) ?? 50

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  })

  try {
    const events = await readActivityLog()
    const snapshot = events.slice(0, limit)
    res.write('event: snapshot\n')
    res.write(`data: ${JSON.stringify({ events: snapshot })}\n\n`)
  } catch (error) {
    console.error('[activity] failed to stream snapshot', error)
    res.write('event: error\n')
    res.write(`data: ${JSON.stringify({ message: 'Failed to load activity history' })}\n\n`)
  }

  const listener = (event) => {
    res.write('event: activity\n')
    res.write(`data: ${JSON.stringify({ event })}\n\n`)
  }

  activityEmitter.on('event', listener)

  const keepAlive = setInterval(() => {
    res.write(': keep-alive\n\n')
  }, 25_000)

  req.on('close', () => {
    clearInterval(keepAlive)
    activityEmitter.off('event', listener)
  })
})

app.post('/api/hil/approvals', csrfProtection, async (req, res) => {
  const payload = req.body ?? {}
  if (!isRecord(payload)) {
    return sendError(res, 400, 'Invalid payload')
  }
  const runId = typeof payload.runId === 'string' && payload.runId.trim().length > 0 ? payload.runId.trim() : undefined
  const status = typeof payload.status === 'string' ? payload.status.toLowerCase() : undefined
  const operator = typeof payload.operator === 'string' && payload.operator.trim().length > 0 ? payload.operator.trim() : undefined
  const comment = typeof payload.comment === 'string' && payload.comment.trim().length > 0 ? payload.comment.trim() : undefined
  const reason = typeof payload.reason === 'string' && payload.reason.trim().length > 0 ? payload.reason.trim() : undefined

  if (!runId) {
    return sendError(res, 422, 'runId is required')
  }
  if (!status || !hilStatusSet.has(status)) {
    return sendError(res, 422, 'status must be one of waiting, approved, rejected')
  }
  if (!operator) {
    return sendError(res, 422, 'operator is required')
  }

  try {
    const approvals = await readHilApprovals()
    const previous = approvals[runId] ?? null
    const approval = createHilApproval({ runId, status, operator, comment, reason })
    approvals[runId] = approval
    await writeHilApprovals(approvals)

    const auditEntry = createHilAuditEntry({
      runId,
      operator,
      action: status,
      comment: comment ?? reason,
      previousStatus: previous?.status ?? null,
      newStatus: status,
    })
    const auditLog = await readHilAudit()
    const updatedAudit = [auditEntry, ...auditLog].slice(0, Number.parseInt(process.env.HOTPASS_HIL_AUDIT_LIMIT ?? '500', 10))
    await writeHilAudit(updatedAudit)

    await appendActivityEvent(createActivityEvent({
      category: 'hil',
      action: status,
      runId,
      operator,
      status,
      success: status !== 'rejected',
      comment: comment ?? undefined,
      reason: reason ?? undefined,
    }))

    res.status(201).json({ approval })
  } catch (error) {
    console.error('[hil] failed to update approvals', error)
    sendError(res, 500, 'Failed to update approval', { message: error.message })
  }
})

app.get('/api/jobs/:id/artifacts', async (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  if (!isImportJob(job)) {
    return sendError(res, 400, 'Artifacts are only available for import jobs')
  }
  try {
    const artifacts = await enumerateImportArtifacts(job)
    res.json({ artifacts })
  } catch (error) {
    console.error('[import] failed to enumerate artifacts', error)
    sendError(res, 500, 'Failed to enumerate artifacts', { message: error.message })
  }
})

app.get('/api/jobs/:id/artifacts/profile', async (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  if (!isImportJob(job)) {
    return sendError(res, 400, 'Artifact available for import jobs only')
  }
  const attachment = job.metadata?.profileAttachment
  if (!attachment || typeof attachment.path !== 'string') {
    return sendError(res, 404, 'Profile artifact unavailable')
  }
  const resolvedPath = path.resolve(attachment.path)
  const allowedRoot = path.resolve(IMPORT_ROOT)
  if (!resolvedPath.startsWith(allowedRoot)) {
    return sendError(res, 403, 'Profile artifact outside import directory')
  }
  try {
    const stats = await stat(resolvedPath)
    if (!stats.isFile()) {
      return sendError(res, 404, 'Profile artifact missing')
    }
    res.setHeader('Content-Type', 'application/json')
    res.setHeader('Content-Length', stats.size)
    res.setHeader('Content-Disposition', `attachment; filename="${attachment.name || path.basename(resolvedPath)}"`)
    fs.createReadStream(resolvedPath).pipe(res)
  } catch (error) {
    if (error.code === 'ENOENT') {
      return sendError(res, 404, 'Profile artifact missing')
    }
    console.error('[import] failed to stream profile artifact', error)
    sendError(res, 500, 'Failed to stream profile artifact', { message: error.message })
  }
})

app.get('/api/jobs/:id/artifacts/contract', async (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  const attachment = job.metadata?.contractAttachment
  if (!attachment || typeof attachment.path !== 'string') {
    return sendError(res, 404, 'Contract artifact unavailable')
  }
  const resolvedPath = path.resolve(attachment.path)
  const allowedRoot = path.resolve(process.cwd(), 'dist', 'contracts')
  if (!resolvedPath.startsWith(allowedRoot)) {
    return sendError(res, 403, 'Contract artifact outside contracts directory')
  }
  try {
    const stats = await stat(resolvedPath)
    if (!stats.isFile()) {
      return sendError(res, 404, 'Contract artifact missing')
    }
    res.setHeader('Content-Type', attachment.format === 'json' ? 'application/json' : 'application/x-yaml')
    res.setHeader('Content-Length', stats.size)
    res.setHeader('Content-Disposition', `attachment; filename="${attachment.name || path.basename(resolvedPath)}"`)
    fs.createReadStream(resolvedPath).pipe(res)
  } catch (error) {
    if (error.code === 'ENOENT') {
      return sendError(res, 404, 'Contract artifact missing')
    }
    console.error('[contracts] failed to stream contract artifact', error)
    sendError(res, 500, 'Failed to stream contract artifact', { message: error.message })
  }
})

app.get('/api/jobs/:id/artifacts/refined', async (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  if (!isImportJob(job)) {
    return sendError(res, 400, 'Artifact available for import jobs only')
  }
  const outputPath = typeof job.metadata.outputPath === 'string' ? job.metadata.outputPath : null
  if (!outputPath) {
    return sendError(res, 404, 'Artifact not found')
  }
  try {
    const stats = await stat(outputPath)
    if (!stats.isFile()) {
      return sendError(res, 404, 'Artifact not found')
    }
    res.setHeader('Content-Type', 'application/octet-stream')
    res.setHeader('Content-Length', stats.size)
    res.setHeader('Content-Disposition', `attachment; filename="${path.basename(outputPath)}"`)
    fs.createReadStream(outputPath).pipe(res)
  } catch (error) {
    if (error.code === 'ENOENT') {
      return sendError(res, 404, 'Artifact not found')
    }
    console.error('[import] failed to stream refined artifact', error)
    sendError(res, 500, 'Failed to stream artifact', { message: error.message })
  }
})

app.get('/api/jobs/:id/artifacts/archive/:filename', async (req, res) => {
  const job = getJob(req.params.id)
  if (!job) {
    return sendError(res, 404, 'Job not found')
  }
  if (!isImportJob(job)) {
    return sendError(res, 400, 'Artifact available for import jobs only')
  }
  const archiveDir = typeof job.metadata.archiveDir === 'string' ? job.metadata.archiveDir : null
  if (!archiveDir) {
    return sendError(res, 404, 'Artifact not found')
  }
  const safeFilename = path.basename(req.params.filename)
  const archivePath = path.join(archiveDir, safeFilename)
  try {
    const stats = await stat(archivePath)
    if (!stats.isFile()) {
      return sendError(res, 404, 'Artifact not found')
    }
    res.setHeader('Content-Type', 'application/octet-stream')
    res.setHeader('Content-Length', stats.size)
    res.setHeader('Content-Disposition', `attachment; filename="${safeFilename}"`)
    fs.createReadStream(archivePath).pipe(res)
  } catch (error) {
    if (error.code === 'ENOENT') {
      return sendError(res, 404, 'Artifact not found')
    }
    console.error('[import] failed to stream archive artifact', error)
    sendError(res, 500, 'Failed to stream artifact', { message: error.message })
  }
})

app.use(express.static(path.join(__dirname, '..', 'dist'), { maxAge: '1d', index: false }))

app.get('/health', (_req, res) => {
  const jobs = listJobs()
  const runningJobs = jobs.filter(job => job.status === 'running').length
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    jobs: {
      total: jobs.length,
      running: runningJobs,
    },
    timestamps: {
      serverStartedAt: jobs.length > 0 ? jobs[jobs.length - 1]?.createdAt ?? null : null,
      checkedAt: new Date().toISOString(),
    },
  })
})

app.use((req, res, next) => {
  if (req.method !== 'GET') {
    return next()
  }

  if (req.path.startsWith('/api/') || req.path.startsWith('/telemetry/') || req.path === '/health') {
    return next()
  }

  res.sendFile(path.join(__dirname, '..', 'dist', 'index.html'))
})

if (process.env.NODE_ENV !== 'test') {
  app.listen(port, () => {
    console.log(`Hotpass UI server listening on port ${port}`)
  })
}
