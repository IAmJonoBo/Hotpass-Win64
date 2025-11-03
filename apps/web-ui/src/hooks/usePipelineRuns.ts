import { useQuery } from '@tanstack/react-query'
import type { PipelineRunResponse } from '@/types'

const DEFAULT_LIMIT = 70
const REFRESH_INTERVAL = 15_000

const fetchPipelineRuns = async (limit = DEFAULT_LIMIT): Promise<PipelineRunResponse> => {
  const response = await fetch(`/api/runs/recent?limit=${encodeURIComponent(limit)}`, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Failed to load recent runs (${response.status})`)
  }

  const payload = (await response.json()) as PipelineRunResponse
  if (!payload || !Array.isArray(payload.runs)) {
    throw new Error('Received an unexpected response for recent runs')
  }
  return payload
}

export function usePipelineRuns(limit = DEFAULT_LIMIT) {
  return useQuery<PipelineRunResponse>({
    queryKey: ['pipeline-runs', limit],
    queryFn: () => fetchPipelineRuns(limit),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: REFRESH_INTERVAL,
  })
}
