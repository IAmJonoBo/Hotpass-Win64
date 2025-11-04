import { useQuery } from '@tanstack/react-query'
import type { QAResult } from '@/types'

export interface QaLatestResponse {
  summary: {
    timestamp?: string
    results?: Array<Record<string, unknown>>
    data_docs?: string
    [key: string]: unknown
  }
  dataDocsPath?: string | null
}

export interface QaLatestData {
  timestamp?: string
  dataDocsPath?: string | null
  results: QAResult[]
  raw: QaLatestResponse
}

const transformResult = (rawResults?: Array<Record<string, unknown>>): QAResult[] => {
  if (!Array.isArray(rawResults)) {
    return []
  }
  return rawResults.map((entry, index) => {
    const checkpoint = typeof entry?.checkpoint === 'string' ? entry.checkpoint : `checkpoint-${index + 1}`
    const statusRaw = typeof entry?.status === 'string' ? entry.status.toLowerCase() : 'passed'
    const status: QAResult['status'] =
      statusRaw === 'failed'
        ? 'failed'
        : statusRaw === 'warning'
          ? 'warning'
          : 'passed'
    return {
      check: checkpoint,
      status,
      message: typeof entry?.message === 'string' ? entry.message : undefined,
      details: entry,
    }
  })
}

export async function fetchLatestQaSummary(): Promise<QaLatestData> {
  const response = await fetch('/api/qa/latest', {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    let message = response.statusText || 'Failed to load QA summary'
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

  const payload = await response.json() as QaLatestResponse
  const results = transformResult(payload.summary?.results as Array<Record<string, unknown>>)
  return {
    timestamp: typeof payload.summary?.timestamp === 'string' ? payload.summary.timestamp : undefined,
    dataDocsPath: typeof payload.dataDocsPath === 'string' ? payload.dataDocsPath : null,
    results,
    raw: payload,
  }
}

export function useLatestQaSummary() {
  return useQuery({
    queryKey: ['qa', 'latest'],
    queryFn: fetchLatestQaSummary,
    staleTime: 30_000,
  })
}
