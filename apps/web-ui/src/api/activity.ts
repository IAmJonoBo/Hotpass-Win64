import type { ActivityEvent } from '@/types'

const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

interface ActivityResponse {
  events?: ActivityEvent[]
}

export async function fetchActivityEvents(limit = 50): Promise<ActivityEvent[]> {
  const params = new URLSearchParams()
  if (limit && Number.isFinite(limit)) {
    params.set('limit', String(limit))
  }
  const response = await fetch(`/api/activity${params.size ? `?${params.toString()}` : ''}`, {
    method: 'GET',
    headers: jsonHeaders,
    credentials: 'include',
  })
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
    throw new Error(message || `Failed to load activity events (${response.status})`)
  }
  const payload: ActivityResponse = await response.json()
  if (payload && Array.isArray(payload.events)) {
    return payload.events
  }
  return []
}
