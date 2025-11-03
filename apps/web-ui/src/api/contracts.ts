import { useQuery } from '@tanstack/react-query'
import { createRateLimiter } from '@/lib/security'

export interface ContractSummary {
  id: string
  name: string
  profile: string
  format: string
  size: number
  updatedAt: string
  downloadUrl: string
}

const limiter = createRateLimiter(6, 30_000)

const fetchWithLimiter = <T>(input: RequestInfo | URL, init?: RequestInit) =>
  limiter(async () => {
    const response = await fetch(input, {
      credentials: 'include',
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
    })
    if (!response.ok) {
      throw new Error(response.statusText || 'Failed to fetch contracts')
    }
    return response.json() as Promise<T>
  })

export async function listContracts(): Promise<ContractSummary[]> {
  const payload = await fetchWithLimiter<{ contracts?: ContractSummary[] }>(
    '/api/contracts',
  )
  if (!payload || !Array.isArray(payload.contracts)) {
    return []
  }
  return payload.contracts
}

export function useContracts() {
  return useQuery({
    queryKey: ['contracts'],
    queryFn: listContracts,
    staleTime: 60_000,
  })
}
