import type { CommandJob } from '@/types'
import { ensureCsrfToken } from './csrf'

const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

export interface RunCommandJobOptions {
  command: string[]
  label?: string
  cwd?: string
  metadata?: Record<string, unknown>
  env?: Record<string, string>
}

export interface CommandJobLinks {
  jobId: string
  statusUrl: string
  logUrl: string
}

export function buildCommandJobLinks(jobId: string): CommandJobLinks {
  return {
    jobId,
    statusUrl: `/api/jobs/${encodeURIComponent(jobId)}`,
    logUrl: `/api/jobs/${encodeURIComponent(jobId)}/events`,
  }
}

export async function runCommandJob(options: RunCommandJobOptions): Promise<CommandJob> {
  if (!Array.isArray(options.command) || options.command.length === 0) {
    throw new Error('Command payload must include a non-empty command array')
  }

  const token = await ensureCsrfToken()
  const response = await fetch('/api/commands/run', {
    method: 'POST',
    headers: {
      ...jsonHeaders,
      'Content-Type': 'application/json',
      'X-CSRF-Token': token,
    },
    credentials: 'include',
    body: JSON.stringify(options),
  })

  if (!response.ok) {
    let message = response.statusText || 'Failed to start command'
    try {
      const payload = await response.json()
      if (payload && typeof payload.error === 'string') {
        message = payload.error
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }

  const payload = await response.json() as { job?: CommandJob }
  if (!payload?.job) {
    throw new Error('Command response malformed')
  }
  return payload.job
}
