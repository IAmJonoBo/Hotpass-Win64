import type { HILApproval, HILAuditEntry } from '@/types'

const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

let cachedCsrfToken: string | null = null

const handleResponse = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    let message = response.statusText
    try {
      const payload = await response.json()
      if (payload && typeof payload.error === 'string') {
        message = payload.error
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message || `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function fetchHilApprovals(): Promise<Record<string, HILApproval>> {
  const response = await fetch('/api/hil/approvals', {
    method: 'GET',
    headers: jsonHeaders,
    credentials: 'include',
  })
  const payload = await handleResponse<{ approvals?: Record<string, HILApproval> }>(response)
  if (payload && payload.approvals && typeof payload.approvals === 'object') {
    return payload.approvals
  }
  return {}
}

export async function fetchHilAudit(limit?: number): Promise<HILAuditEntry[]> {
  const params = new URLSearchParams()
  if (limit && Number.isFinite(limit)) {
    params.set('limit', String(limit))
  }
  const response = await fetch(`/api/hil/audit${params.size ? `?${params.toString()}` : ''}`, {
    method: 'GET',
    headers: jsonHeaders,
    credentials: 'include',
  })
  const payload = await handleResponse<{ entries?: HILAuditEntry[] }>(response)
  if (payload && Array.isArray(payload.entries)) {
    return payload.entries
  }
  return []
}

async function ensureCsrfToken(): Promise<string> {
  if (cachedCsrfToken) {
    return cachedCsrfToken
  }
  const response = await fetch('/telemetry/operator-feedback/csrf', {
    method: 'GET',
    headers: jsonHeaders,
    credentials: 'include',
  })
  const payload = await handleResponse<{ token?: string }>(response)
  if (!payload?.token) {
    throw new Error('Failed to initialise secure session')
  }
  cachedCsrfToken = payload.token
  return cachedCsrfToken
}

interface SubmitApprovalOptions {
  runId: string
  status: 'waiting' | 'approved' | 'rejected'
  operator: string
  comment?: string
  reason?: string
}

export async function submitHilApproval(options: SubmitApprovalOptions): Promise<HILApproval> {
  const token = await ensureCsrfToken()
  const response = await fetch('/api/hil/approvals', {
    method: 'POST',
    headers: {
      ...jsonHeaders,
      'Content-Type': 'application/json',
      'X-CSRF-Token': token,
    },
    credentials: 'include',
    body: JSON.stringify(options),
  })
  const payload = await handleResponse<{ approval?: HILApproval }>(response)
  if (!payload?.approval) {
    throw new Error('Approval response malformed')
  }
  return payload.approval
}
