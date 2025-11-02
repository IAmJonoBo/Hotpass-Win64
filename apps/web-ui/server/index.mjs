import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'
import compression from 'compression'
import helmet from 'helmet'
import cookieParser from 'cookie-parser'
import csrf from 'csurf'
import rateLimit from 'express-rate-limit'
import { createProxyMiddleware } from 'http-proxy-middleware'
import {
  createCommandJob,
  getJob,
  listJobs,
  subscribeToJob,
} from './job-runner.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()

const port = process.env.PORT || 3000
const prefectTarget = process.env.PREFECT_API_URL || process.env.VITE_PREFECT_API_URL || 'http://localhost:4200/api'
const marquezTarget = process.env.MARQUEZ_API_URL || process.env.VITE_MARQUEZ_API_URL || process.env.OPENLINEAGE_URL || 'http://localhost:5000/api/v1'

const prefectLimit = Number.parseInt(process.env.PREFECT_RATE_LIMIT ?? '120', 10)
const marquezLimit = Number.parseInt(process.env.MARQUEZ_RATE_LIMIT ?? '60', 10)

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
