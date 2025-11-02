import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'
import compression from 'compression'
import helmet from 'helmet'
import cookieParser from 'cookie-parser'
import csrf from 'csurf'
import rateLimit from 'express-rate-limit'
import { createProxyMiddleware } from 'http-proxy-middleware'

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

app.use(express.static(path.join(__dirname, '..', 'dist'), { maxAge: '1d', index: false }))

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' })
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
