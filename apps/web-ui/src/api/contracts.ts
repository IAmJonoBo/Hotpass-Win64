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

export interface ContractRuleReference {
  ruleId: string
  contract: {
    id: string
    name: string
    format: string
    updatedAt: string
    downloadUrl: string
  }
  snippet?: string | null
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

export async function getContractRule(ruleId: string): Promise<ContractRuleReference> {
  if (!ruleId || ruleId.trim().length === 0) {
    throw new Error('Rule identifier is required')
  }
  const response = await fetch(`/api/contracts/rules/${encodeURIComponent(ruleId)}`, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
    },
  })
  if (!response.ok) {
    let message = response.statusText || 'Failed to resolve rule reference'
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
  const payload = await response.json() as ContractRuleReference
  return payload
}

export function useContractRule(ruleId?: string | null) {
  return useQuery({
    queryKey: ['contract-rule', ruleId],
    queryFn: () => getContractRule(ruleId ?? ''),
    enabled: Boolean(ruleId && ruleId.trim().length > 0),
    staleTime: 5 * 60_000,
  })
}
