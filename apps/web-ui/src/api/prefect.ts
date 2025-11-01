/**
 * Prefect API client
 *
 * Fetches flow and flow run data from Prefect Cloud/Server.
 * Base URL configured via PREFECT_API_URL (shared with CLI) or VITE_PREFECT_API_URL.
 *
 * ASSUMPTION: Prefect API is available at the configured URL (default: http://localhost:4200)
 * ASSUMPTION: API key authentication handled via proxy or environment
 */

import type {
  PrefectFlow,
  PrefectFlowRun,
  PrefectDeployment,
} from '@/types'

const getBaseUrl = (): string => {
  return (
    import.meta.env.PREFECT_API_URL ||
    import.meta.env.VITE_PREFECT_API_URL ||
    '/api/prefect'
  )
}

export const prefectApi = {
  // List flows
  async getFlows(limit = 100, offset = 0): Promise<PrefectFlow[]> {
    const url = `${getBaseUrl()}/flows?limit=${limit}&offset=${offset}`
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Failed to fetch flows: ${response.statusText}`)
    }
    return response.json()
  },

  // Get a specific flow
  async getFlow(flowId: string): Promise<PrefectFlow> {
    const url = `${getBaseUrl()}/flows/${encodeURIComponent(flowId)}`
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Failed to fetch flow: ${response.statusText}`)
    }
    return response.json()
  },

  // List flow runs (with optional filters)
  async getFlowRuns(params?: {
    flowId?: string
    deploymentId?: string
    state?: string
    limit?: number
    offset?: number
  }): Promise<PrefectFlowRun[]> {
    const queryParams = new URLSearchParams()
    if (params?.flowId) queryParams.append('flow_id', params.flowId)
    if (params?.deploymentId) queryParams.append('deployment_id', params.deploymentId)
    if (params?.state) queryParams.append('state', params.state)
    queryParams.append('limit', String(params?.limit || 100))
    queryParams.append('offset', String(params?.offset || 0))

    const url = `${getBaseUrl()}/flow_runs?${queryParams}`
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Failed to fetch flow runs: ${response.statusText}`)
    }
    return response.json()
  },

  // Get a specific flow run
  async getFlowRun(flowRunId: string): Promise<PrefectFlowRun> {
    const url = `${getBaseUrl()}/flow_runs/${encodeURIComponent(flowRunId)}`
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Failed to fetch flow run: ${response.statusText}`)
    }
    return response.json()
  },

  // List deployments
  async getDeployments(limit = 100, offset = 0): Promise<PrefectDeployment[]> {
    const url = `${getBaseUrl()}/deployments?limit=${limit}&offset=${offset}`
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      throw new Error(`Failed to fetch deployments: ${response.statusText}`)
    }
    return response.json()
  },

  async checkHealth(): Promise<boolean> {
    const url = `${getBaseUrl()}/health`
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'include' })
      if (!response.ok) {
        return false
      }
      const payload = await response.json().catch(() => null)
      if (payload && typeof payload === 'object') {
        if ('status' in payload) {
          return String(payload.status).toLowerCase() === 'healthy'
        }
        if ('healthy' in payload) {
          return Boolean(payload.healthy)
        }
      }
      return true
    } catch (error) {
      console.warn('Prefect health check failed:', error)
      return false
    }
  },
}

// Mock data for development when Prefect is not available
export const mockPrefectData = {
  flows: [
    {
      id: 'flow-001',
      name: 'hotpass-refine',
      created: '2024-01-01T00:00:00Z',
      updated: '2024-01-15T00:00:00Z',
      tags: ['hotpass', 'pipeline'],
    },
    {
      id: 'flow-002',
      name: 'hotpass-enrich',
      created: '2024-01-01T00:00:00Z',
      updated: '2024-01-15T00:00:00Z',
      tags: ['hotpass', 'pipeline'],
    },
  ] as PrefectFlow[],

  flowRuns: [
    {
      id: 'run-001',
      name: 'hotpass-refine-20240115-120000',
      flow_id: 'flow-001',
      state_type: 'COMPLETED',
      state_name: 'Completed',
      start_time: '2024-01-15T12:00:00Z',
      end_time: '2024-01-15T12:30:00Z',
      total_run_time: 1800,
      created: '2024-01-15T11:59:55Z',
      updated: '2024-01-15T12:30:05Z',
      tags: ['aviation'],
      parameters: { profile: 'aviation', input_dir: './data' },
    },
    {
      id: 'run-002',
      name: 'hotpass-enrich-20240115-130000',
      flow_id: 'flow-002',
      state_type: 'COMPLETED',
      state_name: 'Completed',
      start_time: '2024-01-15T13:00:00Z',
      end_time: '2024-01-15T13:45:00Z',
      total_run_time: 2700,
      created: '2024-01-15T12:59:55Z',
      updated: '2024-01-15T13:45:05Z',
      tags: ['aviation'],
      parameters: { profile: 'aviation', allow_network: false },
    },
    {
      id: 'run-003',
      name: 'hotpass-refine-20240115-140000',
      flow_id: 'flow-001',
      state_type: 'RUNNING',
      state_name: 'Running',
      start_time: '2024-01-15T14:00:00Z',
      created: '2024-01-15T13:59:55Z',
      updated: '2024-01-15T14:15:00Z',
      tags: ['generic'],
      parameters: { profile: 'generic', input_dir: './data' },
    },
  ] as PrefectFlowRun[],
}
