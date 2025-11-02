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
import { copyFile, mkdir, mkdtemp, readdir, rm, rename, stat } from 'fs/promises'
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
  appendActivityEvent,
  readActivityLog,
  readHilApprovals,
  readHilAudit,
  writeHilApprovals,
  writeHilAudit,
} from './storage.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()

const port = process.env.PORT || 3000
const prefectTarget = process.env.PREFECT_API_URL || process.env.VITE_PREFECT_API_URL || 'http://localhost:4200/api'
const marquezTarget = process.env.MARQUEZ_API_URL || process.env.VITE_MARQUEZ_API_URL || process.env.OPENLINEAGE_URL || 'http://localhost:5000/api/v1'

const prefectLimit = Number.parseInt(process.env.PREFECT_RATE_LIMIT ?? '120', 10)
const marquezLimit = Number.parseInt(process.env.MARQUEZ_RATE_LIMIT ?? '60', 10)
const IMPORT_ROOT = process.env.HOTPASS_IMPORT_ROOT || path.join(process.cwd(), 'dist', 'import')
const MAX_IMPORT_FILE_SIZE = Number.parseInt(process.env.HOTPASS_IMPORT_MAX_FILE_SIZE ?? `${1024 * 1024 * 1024}`, 10)
const MAX_IMPORT_FILES = Number.parseInt(process.env.HOTPASS_IMPORT_MAX_FILES ?? '10', 10)

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

app.listen(port, () => {
  console.log(`Hotpass UI server listening on port ${port}`)
})
