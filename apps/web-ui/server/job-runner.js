import { spawn } from 'child_process'
import { EventEmitter } from 'events'
import crypto from 'crypto'
import path from 'path'

const jobs = new Map()
const jobEvents = new EventEmitter()

jobEvents.setMaxListeners(0)

const MAX_LOG_ENTRIES = Number.parseInt(process.env.HOTPASS_MAX_JOB_LOGS ?? '2000', 10)
const DEFAULT_CWD = process.cwd()

const createJobId = () => crypto.randomUUID?.() ?? `job-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`

const normaliseCommand = (command) => {
  if (Array.isArray(command)) {
    const [cmd, ...args] = command
    return { cmd, args }
  }
  if (typeof command === 'string') {
    return { cmd: command, args: [] }
  }
  throw new Error('Invalid command type')
}

const pushLog = (job, entry) => {
  job.log.push(entry)
  if (job.log.length > MAX_LOG_ENTRIES) {
    job.log.shift()
    job.logShifted = true
  }
}

const emitForJob = (jobId, payload) => {
  jobEvents.emit(jobId, payload)
  jobEvents.emit('*', { jobId, ...payload })
}

export function listJobs() {
  return Array.from(jobs.values()).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
}

export function getJob(jobId) {
  return jobs.get(jobId) ?? null
}

export function subscribeToJob(jobId, handler) {
  const listener = (payload) => handler(payload)
  jobEvents.on(jobId, listener)
  return () => jobEvents.off(jobId, listener)
}

export function createCommandJob({
  command,
  cwd = DEFAULT_CWD,
  env = {},
  metadata = {},
  label,
}) {
  if (!command) {
    throw new Error('Command is required')
  }

  const { cmd, args } = normaliseCommand(command)
  const jobId = createJobId()
  const createdAt = new Date().toISOString()

  const job = {
    id: jobId,
    label: label || `${cmd} ${args.join(' ')}`.trim(),
    command: [cmd, ...args],
    cwd: path.resolve(cwd),
    env: { ...process.env, ...env },
    status: 'queued',
    createdAt,
    updatedAt: createdAt,
    log: [],
    logShifted: false,
    exitCode: null,
    error: null,
    metadata,
  }

  jobs.set(jobId, job)

  emitForJob(jobId, { type: 'queued', job })

  const child = spawn(cmd, args, {
    cwd: job.cwd,
    env: job.env,
    shell: process.platform === 'win32',
  })

  job.pid = child.pid
  job.status = 'running'
  job.startedAt = new Date().toISOString()
  job.updatedAt = job.startedAt

  emitForJob(jobId, { type: 'started', job })

  child.stdout?.on('data', (data) => {
    const message = data.toString()
    const logEntry = {
      type: 'stdout',
      message,
      timestamp: new Date().toISOString(),
    }
    pushLog(job, logEntry)
    job.updatedAt = logEntry.timestamp
    emitForJob(jobId, { type: 'log', stream: 'stdout', message })
  })

  child.stderr?.on('data', (data) => {
    const message = data.toString()
    const logEntry = {
      type: 'stderr',
      message,
      timestamp: new Date().toISOString(),
    }
    pushLog(job, logEntry)
    job.updatedAt = logEntry.timestamp
    emitForJob(jobId, { type: 'log', stream: 'stderr', message })
  })

  child.on('error', (error) => {
    job.status = 'failed'
    job.error = error.message
    job.updatedAt = new Date().toISOString()
    pushLog(job, {
      type: 'error',
      message: error.message,
      timestamp: job.updatedAt,
    })
    emitForJob(jobId, { type: 'error', error: error.message })
    emitForJob(jobId, { type: 'finished', status: job.status, exitCode: null })
  })

  child.on('close', (code, signal) => {
    job.exitCode = code
    job.signal = signal ?? null
    job.completedAt = new Date().toISOString()
    job.updatedAt = job.completedAt
    job.status = code === 0 ? 'succeeded' : 'failed'
    emitForJob(jobId, { type: 'finished', status: job.status, exitCode: code, signal })
  })

  return job
}
