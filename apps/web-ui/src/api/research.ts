import { useQuery } from '@tanstack/react-query'
import { createRateLimiter } from '@/lib/security'
import type { ResearchRecord } from '@/types'

const BASE_PATH = '/api/research'
const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

const fetchLimiter = createRateLimiter(10, 30_000)

const limitedFetch = <T = unknown>(input: RequestInfo | URL, init: RequestInit = {}): Promise<T> =>
  fetchLimiter(async () => {
    const response = await fetch(input, {
      credentials: 'include',
      ...init,
      headers: {
        ...jsonHeaders,
        ...(init.headers ?? {}),
      },
    })
    if (!response.ok) {
      let message = response.statusText || 'Request failed'
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
    const contentType = response.headers.get('Content-Type') ?? ''
    if (contentType.includes('application/json')) {
      return response.json() as Promise<T>
    }
    return undefined as T
  })

interface ResearchMetadataResponse {
  items?: ResearchRecord[]
}

export const researchApi = {
  async listMetadata(): Promise<ResearchRecord[]> {
    const payload = await limitedFetch<ResearchMetadataResponse>(`${BASE_PATH}/metadata`)
    return Array.isArray(payload?.items) ? payload.items : []
  },

  async getRecord(slug: string): Promise<ResearchRecord | null> {
    if (!slug) return null
    return limitedFetch<ResearchRecord>(`${BASE_PATH}/metadata/${encodeURIComponent(slug)}`)
  },
}

export function useResearchMetadata() {
  return useQuery({
    queryKey: ['research-metadata'],
    queryFn: () => researchApi.listMetadata(),
    staleTime: 60_000,
  })
}
