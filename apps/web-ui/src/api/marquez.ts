/**
 * Marquez/OpenLineage API client
 *
 * Fetches lineage data from the Marquez backend.
 * Base URL configured via OPENLINEAGE_URL (shared with CLI) or VITE_MARQUEZ_API_URL.
 *
 * ASSUMPTION: Marquez is available at the configured URL (default: http://localhost:5000)
 * ASSUMPTION: API follows standard Marquez v1 endpoints
 */

import type {
  MarquezNamespace,
  MarquezJob,
  MarquezDataset,
  MarquezRun,
  MarquezLineageGraph,
  MarquezLineageGraphNode,
  MarquezLineageGraphEdge,
  MarquezLineageFilters,
} from '@/types'

type LineageUpdateHandler = (graph: MarquezLineageGraph) => void
type LineageErrorHandler = (error: unknown) => void

export interface LineageSubscription {
  close: () => void
  mode: 'websocket' | 'polling'
}

export interface LineageSubscriptionOptions extends MarquezLineageFilters {
  onUpdate: LineageUpdateHandler
  onError?: LineageErrorHandler
  pollIntervalMs?: number
  onModeChange?: (mode: 'websocket' | 'polling') => void
}

interface LineagePollerOptions {
  intervalMs?: number
  onError?: LineageErrorHandler
  immediate?: boolean
}

const ensureAbsoluteUrl = (url: string): URL => {
  if (url.startsWith('http') || url.startsWith('ws')) {
    return new URL(url)
  }
  const base =
    typeof window !== 'undefined' && window.location
      ? window.location.origin
      : 'http://localhost'
  return new URL(url, base)
}

const buildLineageQuery = (filters: MarquezLineageFilters): URL => {
  const base = ensureAbsoluteUrl(`${getBaseUrl()}/api/v1/lineage`)
  const params = base.searchParams
  params.set('nodeType', filters.nodeType)
  params.set('nodeId', `${filters.namespace}:${filters.name}`)
  if (filters.upstreamDepth !== undefined) {
    params.set('upstreamDepth', String(filters.upstreamDepth))
  }
  if (filters.downstreamDepth !== undefined) {
    params.set('downstreamDepth', String(filters.downstreamDepth))
  }
  if (filters.includeDownstream !== undefined) {
    params.set('withDownstream', String(filters.includeDownstream))
  }
  if (filters.includeUpstream !== undefined) {
    params.set('withUpstream', String(filters.includeUpstream))
  }
  if (filters.startTime) {
    params.set('start', filters.startTime)
  }
  if (filters.endTime) {
    params.set('end', filters.endTime)
  }
  if (filters.filterRunStates?.length) {
    params.set('filterRunStates', filters.filterRunStates.join(','))
  }
  return base
}

const toWebSocketUrl = (url: URL): string => {
  const wsUrl = new URL(url.toString())
  wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  return wsUrl.toString()
}

/**
 * ASSUMPTION (see SCRATCH.md): Marquez lineage endpoint returns a JSON payload containing
 * `{ graph: { nodes, edges } }`. This helper normalises partial objects so React Flow always
 * receives id/type/name fields even when optional fields are missing.
 */
const normalizeLineageGraph = (payload: unknown): MarquezLineageGraph => {
  const raw = payload as {
    graph?: {
      nodes?: Array<Partial<MarquezLineageGraphNode>>
      edges?: Array<Partial<MarquezLineageGraphEdge>>
      lastUpdatedAt?: string
    }
    lastUpdatedAt?: string
  }
  const nodes: MarquezLineageGraphNode[] = Array.isArray(raw?.graph?.nodes)
    ? raw.graph.nodes.map((node) => {
        const id = String(node?.id ?? '')
        const [namespacePart, ...rest] = id.split(':')
        const fallbackName = rest.length > 0 ? rest.join(':') : id
        return {
          id,
          type: node?.type === 'JOB' ? 'JOB' : 'DATASET',
          data: {
            ...(node?.data as MarquezDataset | MarquezJob | undefined),
            name: node?.data?.name ?? (node as any)?.name ?? fallbackName,
            namespace:
              node?.data?.namespace ??
              (node as any)?.namespace ??
              (node?.data as MarquezDataset | MarquezJob | undefined)?.id?.namespace ??
              namespacePart,
          },
          run: (node as any)?.run ?? (node?.data as any)?.latestRun ?? null,
        }
      })
    : []
  const edges: MarquezLineageGraphEdge[] = Array.isArray(raw?.graph?.edges)
    ? raw.graph.edges.map((edge) => ({
        origin: String(edge?.origin ?? ''),
        destination: String(edge?.destination ?? ''),
      }))
    : []

  return {
    graph: {
      nodes,
      edges,
    },
    lastUpdatedAt: raw?.lastUpdatedAt ?? raw?.graph?.lastUpdatedAt ?? new Date().toISOString(),
  }
}

const getBaseUrl = (): string => {
  // In production, use proxy path; in dev, vite.config.ts handles the proxy
  return (
    import.meta.env.OPENLINEAGE_URL ||
    import.meta.env.VITE_MARQUEZ_API_URL ||
    '/api/marquez'
  )
}

export const marquezApi = {
  // List all namespaces
  async getNamespaces(): Promise<MarquezNamespace[]> {
    const url = `${getBaseUrl()}/api/v1/namespaces`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch namespaces: ${response.statusText}`)
    }
    const data = await response.json()
    return data.namespaces || []
  },

  // Get jobs in a namespace
  async getJobs(namespace: string, limit = 100, offset = 0): Promise<MarquezJob[]> {
    const url = `${getBaseUrl()}/api/v1/namespaces/${encodeURIComponent(namespace)}/jobs?limit=${limit}&offset=${offset}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch jobs: ${response.statusText}`)
    }
    const data = await response.json()
    return data.jobs || []
  },

  // Get a specific job
  async getJob(namespace: string, jobName: string): Promise<MarquezJob> {
    const url = `${getBaseUrl()}/api/v1/namespaces/${encodeURIComponent(namespace)}/jobs/${encodeURIComponent(jobName)}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch job: ${response.statusText}`)
    }
    return response.json()
  },

  // Get runs for a job
  async getJobRuns(namespace: string, jobName: string, limit = 100, offset = 0): Promise<MarquezRun[]> {
    const url = `${getBaseUrl()}/api/v1/namespaces/${encodeURIComponent(namespace)}/jobs/${encodeURIComponent(jobName)}/runs?limit=${limit}&offset=${offset}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch job runs: ${response.statusText}`)
    }
    const data = await response.json()
    return data.runs || []
  },

  // Get a specific run
  async getRun(runId: string): Promise<MarquezRun> {
    const url = `${getBaseUrl()}/api/v1/runs/${encodeURIComponent(runId)}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch run: ${response.statusText}`)
    }
    return response.json()
  },

  // Get datasets in a namespace
  async getDatasets(namespace: string, limit = 100, offset = 0): Promise<MarquezDataset[]> {
    const url = `${getBaseUrl()}/api/v1/namespaces/${encodeURIComponent(namespace)}/datasets?limit=${limit}&offset=${offset}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch datasets: ${response.statusText}`)
    }
    const data = await response.json()
    return data.datasets || []
  },

  // Get lineage graph with full filter set
  async getLineageGraph(filters: MarquezLineageFilters): Promise<MarquezLineageGraph> {
    const url = buildLineageQuery(filters)
    const response = await fetch(url.toString())
    if (!response.ok) {
      throw new Error(`Failed to fetch lineage: ${response.statusText}`)
    }
    const data = await response.json()
    return normalizeLineageGraph(data)
  },

  // Get lineage for a dataset
  async getDatasetLineage(namespace: string, datasetName: string, depth = 20): Promise<MarquezLineageGraph> {
    return this.getLineageGraph({
      namespace,
      name: datasetName,
      nodeType: 'DATASET',
      upstreamDepth: depth,
      downstreamDepth: depth,
      includeDownstream: true,
      includeUpstream: true,
    })
  },

  // Get lineage for a job
  async getJobLineage(namespace: string, jobName: string, depth = 20): Promise<MarquezLineageGraph> {
    return this.getLineageGraph({
      namespace,
      name: jobName,
      nodeType: 'JOB',
      upstreamDepth: depth,
      downstreamDepth: depth,
      includeDownstream: true,
      includeUpstream: true,
    })
  },

  createLineagePoller(
    filters: MarquezLineageFilters,
    onUpdate: LineageUpdateHandler,
    options: LineagePollerOptions = {},
  ): LineageSubscription {
    let disposed = false
    let timeoutId: ReturnType<typeof setTimeout> | undefined

    const interval = options.intervalMs ?? 30000

    const tick = async () => {
      if (disposed) return
      try {
        const graph = await marquezApi.getLineageGraph(filters)
        onUpdate(graph)
      } catch (error) {
        options.onError?.(error)
      } finally {
        if (!disposed) {
          timeoutId = setTimeout(tick, interval)
        }
      }
    }

    if (options.immediate !== false) {
      void tick()
    } else {
      timeoutId = setTimeout(tick, interval)
    }

    return {
      close() {
        disposed = true
        if (timeoutId) {
          clearTimeout(timeoutId)
        }
      },
      mode: 'polling',
    }
  },

  subscribeToLineage(options: LineageSubscriptionOptions): LineageSubscription {
    const { onUpdate, onError, pollIntervalMs, onModeChange, ...filters } = options

    if (typeof window === 'undefined' || typeof WebSocket === 'undefined') {
      onModeChange?.('polling')
      return this.createLineagePoller(filters, onUpdate, {
        intervalMs: pollIntervalMs ?? 30000,
        onError,
      })
    }

    // ASSUMPTION (documented in SCRATCH): Marquez exposes a websocket bridge at /api/v1/lineage/stream
    // which mirrors the GET /api/v1/lineage response payloads. If it is unavailable we fall back to polling.
    const streamRoot = ensureAbsoluteUrl(`${getBaseUrl()}/api/v1/lineage/stream`)
    const query = buildLineageQuery(filters)
    query.searchParams.forEach((value, key) => {
      streamRoot.searchParams.set(key, value)
    })

    let closed = false
    let pollFallback: LineageSubscription | null = null

    const subscription: LineageSubscription = {
      mode: 'websocket',
      close() {
        closed = true
        ws?.close()
        pollFallback?.close()
      },
    }

    const fallback = (error?: unknown) => {
      if (closed) return
      subscription.mode = 'polling'
      pollFallback = marquezApi.createLineagePoller(filters, onUpdate, {
        intervalMs: pollIntervalMs ?? 30000,
        onError: onError ?? (() => undefined),
      })
      onModeChange?.('polling')
      if (error) {
        onError?.(error)
      }
    }

    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(toWebSocketUrl(streamRoot))
      onModeChange?.('websocket')
    } catch (error) {
      fallback(error)
      return pollFallback ?? subscription
    }

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        const graph = normalizeLineageGraph(payload)
        onUpdate(graph)
      } catch (error) {
        onError?.(error)
      }
    }

    ws.onerror = (event) => {
      onError?.(event)
      if (!closed) {
        ws?.close()
        fallback(event)
      }
    }

    ws.onclose = () => {
      if (!closed) {
        fallback()
      }
    }

    return subscription
  },

  async checkHealth(): Promise<boolean> {
    const base = getBaseUrl()
    try {
      const response = await fetch(`${base}/api/v1/namespaces?limit=1`, {
        headers: { Accept: 'application/json' },
      })
      return response.ok
    } catch (error) {
      console.warn('Marquez health check failed:', error)
      return false
    }
  },
}

// Mock data for development when Marquez is not available
export const mockMarquezData = {
  namespaces: [
    { name: 'hotpass', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-15T00:00:00Z' },
    { name: 'default', createdAt: '2024-01-01T00:00:00Z', updatedAt: '2024-01-15T00:00:00Z' },
  ] as MarquezNamespace[],

  jobs: [
    {
      id: { namespace: 'hotpass', name: 'refine_pipeline' },
      type: 'BATCH',
      name: 'refine_pipeline',
      namespace: 'hotpass',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-15T12:30:00Z',
      latestRun: {
        id: 'run-001',
        createdAt: '2024-01-15T12:00:00Z',
        updatedAt: '2024-01-15T12:30:00Z',
        state: 'COMPLETED',
        startedAt: '2024-01-15T12:00:00Z',
        endedAt: '2024-01-15T12:30:00Z',
        durationMs: 1800000,
      },
    },
    {
      id: { namespace: 'hotpass', name: 'enrich_pipeline' },
      type: 'BATCH',
      name: 'enrich_pipeline',
      namespace: 'hotpass',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-15T13:45:00Z',
      latestRun: {
        id: 'run-002',
        createdAt: '2024-01-15T13:00:00Z',
        updatedAt: '2024-01-15T13:45:00Z',
        state: 'COMPLETED',
        startedAt: '2024-01-15T13:00:00Z',
        endedAt: '2024-01-15T13:45:00Z',
        durationMs: 2700000,
      },
    },
  ] as MarquezJob[],

  datasets: [
    {
      id: { namespace: 'hotpass', name: 'refined_aviation' },
      type: 'TABLE',
      name: 'refined_aviation',
      physicalName: 'hotpass.refined_aviation',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-15T12:30:00Z',
      namespace: 'hotpass',
      sourceName: 'snowflake',
      description: 'Curated aviation facts',
      tags: ['hotpass'],
    },
    {
      id: { namespace: 'hotpass', name: 'enriched_aviation' },
      type: 'TABLE',
      name: 'enriched_aviation',
      physicalName: 'hotpass.enriched_aviation',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-15T13:45:00Z',
      namespace: 'hotpass',
      sourceName: 'snowflake',
      description: 'Enriched aviation entities with provenance facets',
      tags: ['hotpass', 'provenance'],
    },
  ] as MarquezDataset[],

  lineageGraph: {
    graph: {
      nodes: [
        {
          id: 'hotpass:refine_pipeline',
          type: 'JOB',
          data: {
            id: { namespace: 'hotpass', name: 'refine_pipeline' },
            name: 'refine_pipeline',
            namespace: 'hotpass',
            type: 'BATCH',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-15T12:30:00Z',
            latestRun: {
              id: 'run-001',
              createdAt: '2024-01-15T12:00:00Z',
              updatedAt: '2024-01-15T12:30:00Z',
              state: 'COMPLETED',
              startedAt: '2024-01-15T12:00:00Z',
              endedAt: '2024-01-15T12:30:00Z',
            },
          },
          run: {
            id: 'run-001',
            createdAt: '2024-01-15T12:00:00Z',
            updatedAt: '2024-01-15T12:30:00Z',
            state: 'COMPLETED',
            startedAt: '2024-01-15T12:00:00Z',
            endedAt: '2024-01-15T12:30:00Z',
          },
        },
        {
          id: 'hotpass:refined_aviation',
          type: 'DATASET',
          data: {
            id: { namespace: 'hotpass', name: 'refined_aviation' },
            name: 'refined_aviation',
            namespace: 'hotpass',
            type: 'TABLE',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-15T12:30:00Z',
            sourceName: 'snowflake',
            physicalName: 'hotpass.refined_aviation',
          },
        },
        {
          id: 'hotpass:enrich_pipeline',
          type: 'JOB',
          data: {
            id: { namespace: 'hotpass', name: 'enrich_pipeline' },
            name: 'enrich_pipeline',
            namespace: 'hotpass',
            type: 'BATCH',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-15T13:45:00Z',
            latestRun: {
              id: 'run-002',
              createdAt: '2024-01-15T13:00:00Z',
              updatedAt: '2024-01-15T13:45:00Z',
              state: 'COMPLETED',
              startedAt: '2024-01-15T13:00:00Z',
              endedAt: '2024-01-15T13:45:00Z',
            },
          },
          run: {
            id: 'run-002',
            createdAt: '2024-01-15T13:00:00Z',
            updatedAt: '2024-01-15T13:45:00Z',
            state: 'COMPLETED',
            startedAt: '2024-01-15T13:00:00Z',
            endedAt: '2024-01-15T13:45:00Z',
          },
        },
        {
          id: 'hotpass:enriched_aviation',
          type: 'DATASET',
          data: {
            id: { namespace: 'hotpass', name: 'enriched_aviation' },
            name: 'enriched_aviation',
            namespace: 'hotpass',
            type: 'TABLE',
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-15T13:45:00Z',
            sourceName: 'snowflake',
            physicalName: 'hotpass.enriched_aviation',
          },
        },
      ] satisfies MarquezLineageGraphNode[],
      edges: [
        { origin: 'hotpass:refine_pipeline', destination: 'hotpass:refined_aviation' },
        { origin: 'hotpass:refined_aviation', destination: 'hotpass:enrich_pipeline' },
        { origin: 'hotpass:enrich_pipeline', destination: 'hotpass:enriched_aviation' },
      ] satisfies MarquezLineageGraphEdge[],
    },
    lastUpdatedAt: '2024-01-15T15:00:00Z',
  } as MarquezLineageGraph,
}
