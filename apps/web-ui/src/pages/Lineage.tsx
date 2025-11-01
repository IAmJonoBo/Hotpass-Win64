/**
 * Lineage Page
 *
 * Visualises data lineage from Marquez/OpenLineage using React Flow. Operators can
 * filter by namespace, node type, run state, and time window while live updates arrive
 * via WebSocket (falling back to polling when unavailable).
 *
 * ASSUMPTION: Marquez lineage filters accept nodeType/nodeId, upstreamDepth,
 * downstreamDepth, start/end ISO timestamps, and filterRunStates – matching the v1 API.
 */

import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Edge as FlowEdge,
  type Node as FlowNode,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  AlertTriangle,
  Clock,
  Filter,
  GitBranch,
  Layers,
  RefreshCw,
  Search,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { marquezApi, mockMarquezData } from '@/api/marquez'
import type {
  MarquezDataset,
  MarquezJob,
  MarquezLineageGraph,
  MarquezRun,
} from '@/types'
import { cn } from '@/lib/utils'

type NodeType = 'JOB' | 'DATASET'

const RUN_STATE_OPTIONS: Array<MarquezRun['state']> = [
  'COMPLETED',
  'RUNNING',
  'FAILED',
  'ABORTED',
]

const TIME_WINDOWS = [
  { label: '6h', hours: 6 },
  { label: '12h', hours: 12 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 24 * 7 },
] as const

interface ReactFlowElements {
  nodes: FlowNode[]
  edges: FlowEdge[]
  levelMap: Map<string, number>
}

const buildReactFlowElements = (
  graph: MarquezLineageGraph | undefined,
  rootId: string | null,
): ReactFlowElements => {
  if (!graph || !rootId) {
    return { nodes: [], edges: [], levelMap: new Map() }
  }

  const edges = graph.graph.edges ?? []
  const nodes = graph.graph.nodes ?? []
  const levelMap = new Map<string, number>()
  const queue: string[] = []

  if (nodes.some((node) => node.id === rootId)) {
    levelMap.set(rootId, 0)
    queue.push(rootId)
  }

  while (queue.length > 0) {
    const current = queue.shift()!
    const currentLevel = levelMap.get(current) ?? 0

    edges
      .filter((edge) => edge.destination === current)
      .forEach((edge) => {
        if (!levelMap.has(edge.origin)) {
          levelMap.set(edge.origin, currentLevel - 1)
          queue.push(edge.origin)
        }
      })

    edges
      .filter((edge) => edge.origin === current)
      .forEach((edge) => {
        if (!levelMap.has(edge.destination)) {
          levelMap.set(edge.destination, currentLevel + 1)
          queue.push(edge.destination)
        }
      })
  }

  // Place any disconnected nodes on the root column
  nodes.forEach((node) => {
    if (!levelMap.has(node.id)) {
      levelMap.set(node.id, 0)
    }
  })

  const grouped = new Map<number, string[]>()
  levelMap.forEach((level, nodeId) => {
    const list = grouped.get(level) ?? []
    list.push(nodeId)
    grouped.set(level, list)
  })

  grouped.forEach((list, level) => {
    list.sort()
    grouped.set(level, list)
  })

  const xSpacing = 260
  const ySpacing = 140

  const flowNodes: FlowNode[] = nodes.map((node) => {
    const level = levelMap.get(node.id) ?? 0
    const siblings = grouped.get(level) ?? []
    const index = siblings.indexOf(node.id)
    const yOffset = index - (siblings.length - 1) / 2

    const latestRun = node.run
    const runState = latestRun?.state
    const nodeData = node.data
    const subLabel = node.type === 'JOB'
      ? (nodeData as Partial<MarquezJob>).type ?? 'JOB'
      : (nodeData as Partial<MarquezDataset>).sourceName ?? (nodeData as Partial<MarquezDataset>).type ?? 'DATASET'

    return {
      id: node.id,
      type: 'default',
      data: {
        label: node.data.name,
        subLabel,
        latestRun,
      },
      position: {
        x: level * xSpacing,
        y: yOffset * ySpacing,
      },
      style: {
        borderRadius: '1rem',
        padding: 12,
        border:
          node.id === rootId
            ? '2px solid hsl(var(--primary))'
            : '1px solid hsl(var(--border))',
        background: 'hsl(var(--card))',
        color: 'hsl(var(--card-foreground))',
        minWidth: 180,
        boxShadow:
          node.id === rootId
            ? '0 0 0 4px hsla(var(--primary), 0.15)'
            : '0 10px 24px rgba(15,23,42,0.08)',
        fontWeight: node.id === rootId ? 600 : 500,
      },
      className: cn(
        'text-sm',
        runState === 'FAILED' && 'border border-red-400 text-red-500',
        runState === 'RUNNING' && 'border border-blue-400 text-blue-500',
      ),
    }
  })

  const flowEdges: FlowEdge[] = edges.map((edge, index) => ({
    id: `${edge.origin}-${edge.destination}-${index}`,
    source: edge.origin,
    target: edge.destination,
    type: 'smoothstep',
    animated: edge.origin === rootId,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: 'hsl(var(--primary))',
    },
    style: {
      strokeWidth: 2,
    },
  }))

  return { nodes: flowNodes, edges: flowEdges, levelMap }
}

export function Lineage() {
  const queryClient = useQueryClient()
  const defaultNamespace = mockMarquezData.namespaces[0]?.name ?? 'hotpass'

  const [searchTerm, setSearchTerm] = useState('')
  const [selectedNamespace, setSelectedNamespace] = useState(defaultNamespace)
  const [nodeType, setNodeType] = useState<NodeType>('JOB')
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [upstreamDepth, setUpstreamDepth] = useState(2)
  const [downstreamDepth, setDownstreamDepth] = useState(2)
  const [includeUpstream, setIncludeUpstream] = useState(true)
  const [includeDownstream, setIncludeDownstream] = useState(true)
  const [timeWindowHours, setTimeWindowHours] = useState<number>(24)
  const [stateFilters, setStateFilters] = useState<Array<MarquezRun['state']>>([])
  const [subscriptionMode, setSubscriptionMode] = useState<'websocket' | 'polling' | null>(null)
  const [subscriptionError, setSubscriptionError] = useState<string | null>(null)

  const {
    data: namespaces = [],
  } = useQuery({
    queryKey: ['namespaces'],
    queryFn: () => marquezApi.getNamespaces(),
    placeholderData: mockMarquezData.namespaces,
  })

  const {
    data: jobs = [],
    error: jobsError,
  } = useQuery({
    queryKey: ['jobs', selectedNamespace],
    queryFn: () => marquezApi.getJobs(selectedNamespace, 200),
    placeholderData: mockMarquezData.jobs,
    enabled: Boolean(selectedNamespace),
  })

  const {
    data: datasets = [],
    error: datasetsError,
  } = useQuery({
    queryKey: ['datasets', selectedNamespace],
    queryFn: () => marquezApi.getDatasets(selectedNamespace, 200),
    placeholderData: mockMarquezData.datasets,
    enabled: Boolean(selectedNamespace),
  })

  const availableJobs = useMemo(() => {
    if (jobs.length > 0) {
      return jobs
    }
    return jobsError ? mockMarquezData.jobs : []
  }, [jobs, jobsError])

  const availableDatasets = useMemo(() => {
    if (datasets.length > 0) {
      return datasets
    }
    return datasetsError ? mockMarquezData.datasets : []
  }, [datasets, datasetsError])

  const candidates = useMemo(() => {
    return nodeType === 'JOB' ? availableJobs : availableDatasets
  }, [nodeType, availableJobs, availableDatasets])

  const filteredCandidates = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    if (!term) return candidates
    return candidates.filter((entity) =>
      entity.name.toLowerCase().includes(term) ||
      (entity as MarquezJob).namespace?.toLowerCase().includes(term),
    )
  }, [candidates, searchTerm])

  useEffect(() => {
    if (filteredCandidates.length === 0) {
      setSelectedName(null)
      return
    }

    if (!selectedName || !filteredCandidates.some((entity) => entity.name === selectedName)) {
      setSelectedName(filteredCandidates[0].name)
    }
  }, [filteredCandidates, selectedName])

  const selectedEntity = useMemo(() => {
    if (!selectedName) return null
    return candidates.find((entity) => entity.name === selectedName) ?? null
  }, [candidates, selectedName])

  const selectedJob = useMemo(() => {
    if (nodeType !== 'JOB' || !selectedEntity) return null
    return selectedEntity as MarquezJob
  }, [nodeType, selectedEntity])

  const selectedDataset = useMemo(() => {
    if (nodeType !== 'DATASET' || !selectedEntity) return null
    return selectedEntity as MarquezDataset
  }, [nodeType, selectedEntity])

  const sortedStateFilters = useMemo(
    () => [...stateFilters].sort(),
    [stateFilters],
  )

  const now = Date.now()
  const startTime = useMemo(() => {
    const ms = timeWindowHours * 60 * 60 * 1000
    return new Date(now - ms).toISOString()
  }, [now, timeWindowHours])
  const endTime = useMemo(() => new Date(now).toISOString(), [now])

  const lineageFilters = useMemo(() => {
    if (!selectedName) return null
    return {
      namespace: selectedNamespace,
      name: selectedName,
      nodeType,
      upstreamDepth,
      downstreamDepth,
      includeUpstream,
      includeDownstream,
      startTime,
      endTime,
      filterRunStates: sortedStateFilters.length > 0 ? sortedStateFilters : undefined,
    }
  }, [
    selectedNamespace,
    selectedName,
    nodeType,
    upstreamDepth,
    downstreamDepth,
    includeUpstream,
    includeDownstream,
    startTime,
    endTime,
    sortedStateFilters,
  ])

  const lineageQueryKey = useMemo(
    () => [
      'lineage-graph',
      selectedNamespace,
      nodeType,
      selectedName,
      upstreamDepth,
      downstreamDepth,
      includeUpstream,
      includeDownstream,
      timeWindowHours,
      sortedStateFilters.join(','),
    ],
    [
      selectedNamespace,
      nodeType,
      selectedName,
      upstreamDepth,
      downstreamDepth,
      includeUpstream,
      includeDownstream,
      timeWindowHours,
      sortedStateFilters,
    ],
  )

  const {
    data: lineageGraph,
    isFetching: isFetchingLineage,
    error: lineageError,
    refetch: refetchLineage,
  } = useQuery({
    queryKey: lineageQueryKey,
    enabled: Boolean(lineageFilters),
    queryFn: () => marquezApi.getLineageGraph(lineageFilters!),
    placeholderData: mockMarquezData.lineageGraph,
    staleTime: 30000,
  })

  useEffect(() => {
    if (!lineageFilters) return
    setSubscriptionError(null)
    const subscription = marquezApi.subscribeToLineage({
      ...lineageFilters,
      pollIntervalMs: 45000,
      onUpdate: (graph) => {
        queryClient.setQueryData(lineageQueryKey, graph)
      },
      onError: (error) => {
        const message = error instanceof Error
          ? error.message
          : 'Real-time lineage updates encountered an error.'
        setSubscriptionError(message)
      },
      onModeChange: (mode) => setSubscriptionMode(mode),
    })
    setSubscriptionMode(subscription.mode)
    return () => subscription.close()
  }, [lineageFilters, lineageQueryKey, queryClient])

  const rootId = useMemo(() => {
    if (!lineageFilters) return null
    return `${lineageFilters.namespace}:${lineageFilters.name}`
  }, [lineageFilters])

  const { nodes: flowNodes, edges: flowEdges } = useMemo(
    () => buildReactFlowElements(lineageGraph, rootId),
    [lineageGraph, rootId],
  )

  const handleStateToggle = (state: MarquezRun['state']) => {
    setStateFilters((prev) =>
      prev.includes(state) ? prev.filter((item) => item !== state) : [...prev, state],
    )
  }

  const handleNodeClick = (_event: React.MouseEvent, node: FlowNode) => {
    const [namespacePart, ...nameParts] = node.id.split(':')
    const nameFromId = nameParts.join(':') || node.id
    if (namespacePart && namespacePart !== selectedNamespace) {
      setSelectedNamespace(namespacePart)
    }
    setSelectedName(nameFromId)
  }

  const isEmptyGraph = flowNodes.length === 0
  const lineageErrorMessage = lineageError instanceof Error ? lineageError.message : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Data Lineage</h1>
        <p className="text-muted-foreground">
          Explore job and dataset relationships from OpenLineage events with live updates.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
          <CardDescription>
            Marquez lineage parameters map directly to the controls below. Adjust depth,
            time window, and run states to refine the graph.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Namespace
              </label>
              <div className="flex flex-wrap gap-2">
                {namespaces.map((ns) => (
                  <Button
                    key={ns.name}
                    variant={selectedNamespace === ns.name ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedNamespace(ns.name)}
                  >
                    {ns.name}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Node Type
              </label>
              <div className="flex gap-2">
                {(['JOB', 'DATASET'] as const).map((type) => (
                  <Button
                    key={type}
                    variant={nodeType === type ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setNodeType(type)}
                  >
                    {type === 'JOB' ? 'Jobs' : 'Datasets'}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="space-y-2">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Search
              </label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={`Search ${nodeType === 'JOB' ? 'jobs' : 'datasets'}...`}
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Upstream Depth
              </label>
              <Input
                type="number"
                min={0}
                max={20}
                value={upstreamDepth}
                onChange={(event) => setUpstreamDepth(Number(event.target.value))}
              />
              <div className="flex gap-2">
                <Button
                  variant={includeUpstream ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setIncludeUpstream((prev) => !prev)}
                >
                  {includeUpstream ? 'Include Upstream' : 'Exclude Upstream'}
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Downstream Depth
              </label>
              <Input
                type="number"
                min={0}
                max={20}
                value={downstreamDepth}
                onChange={(event) => setDownstreamDepth(Number(event.target.value))}
              />
              <div className="flex gap-2">
                <Button
                  variant={includeDownstream ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setIncludeDownstream((prev) => !prev)}
                >
                  {includeDownstream ? 'Include Downstream' : 'Exclude Downstream'}
                </Button>
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Time Window
              </label>
              <div className="flex flex-wrap gap-2">
                {TIME_WINDOWS.map((window) => (
                  <Button
                    key={window.label}
                    variant={timeWindowHours === window.hours ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTimeWindowHours(window.hours)}
                  >
                    Last {window.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Run States
              </label>
              <div className="flex flex-wrap gap-2">
                {RUN_STATE_OPTIONS.map((state) => (
                  <Button
                    key={state}
                    variant={stateFilters.includes(state) ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleStateToggle(state)}
                  >
                    {state}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {(lineageErrorMessage || subscriptionError || jobsError || datasetsError) && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400 flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div>
            <div className="font-semibold">Lineage fetch issue</div>
            <p className="text-xs text-red-600/80 dark:text-red-300/80">
              {lineageErrorMessage ||
                subscriptionError ||
                (jobsError instanceof Error ? jobsError.message : null) ||
                (datasetsError instanceof Error ? datasetsError.message : null)}
            </p>
          </div>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Lineage Graph
            </CardTitle>
            <CardDescription>
              Click nodes to pivot the graph. Data refreshes automatically via{' '}
              {subscriptionMode === 'polling' ? 'polling' : 'WebSocket'}.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {lineageGraph?.lastUpdatedAt && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Updated {new Date(lineageGraph.lastUpdatedAt).toLocaleString()}
              </span>
            )}
            <Badge
              variant="outline"
              className={cn(
                'flex items-center gap-1',
                subscriptionMode === 'websocket'
                  ? 'border-green-500/40 text-green-600 dark:text-green-400'
                  : 'border-yellow-500/40 text-yellow-600 dark:text-yellow-400',
              )}
            >
              {subscriptionMode === 'websocket' ? (
                <>
                  <Wifi className="h-3 w-3" />
                  Live (WebSocket)
                </>
              ) : (
                <>
                  <WifiOff className="h-3 w-3" />
                  Live (Polling)
                </>
              )}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchLineage()}
              disabled={isFetchingLineage}
            >
              <RefreshCw className={cn('h-4 w-4 mr-2', isFetchingLineage && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="h-[520px]">
          {isFetchingLineage && (
            <div className="mb-3 text-xs text-muted-foreground">
              Fetching latest lineage snapshot...
            </div>
          )}
          {isEmptyGraph ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
              <Layers className="h-6 w-6" />
              No lineage data for the selected filters. Expand the depth or adjust run states.
            </div>
          ) : (
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              onNodeClick={handleNodeClick}
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <MiniMap />
              <Controls />
            </ReactFlow>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="h-4 w-4" />
              Matching Entities
            </CardTitle>
            <CardDescription>
              Click an entity to set it as the lineage root. {filteredCandidates.length} match
              {filteredCandidates.length === 1 ? '' : 'es'} active filters.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
              {filteredCandidates.map((entity) => {
                const isSelected = entity.name === selectedName
                const job = entity as MarquezJob
                return (
                  <button
                    key={`${entity.namespace}:${entity.name}`}
                    onClick={() => setSelectedName(entity.name)}
                    className={cn(
                      'w-full rounded-2xl border px-4 py-3 text-left transition hover:border-primary hover:shadow',
                      isSelected ? 'border-primary bg-primary/5' : 'border-border',
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold text-sm">{entity.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {entity.namespace} · {nodeType === 'JOB' ? job.type : (entity as MarquezDataset).type}
                        </div>
                      </div>
                      {nodeType === 'JOB' && job.latestRun && (
                        <Badge
                          variant="outline"
                          className={cn(
                            job.latestRun.state === 'COMPLETED' && 'text-green-600 dark:text-green-400',
                            job.latestRun.state === 'FAILED' && 'text-red-600 dark:text-red-400',
                            job.latestRun.state === 'RUNNING' && 'text-blue-600 dark:text-blue-400',
                          )}
                        >
                          {job.latestRun.state}
                        </Badge>
                      )}
                    </div>
                  </button>
                )
              })}
              {filteredCandidates.length === 0 && (
                <div className="rounded-2xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
                  No entities found. Clear the search or adjust filters.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Selected Entity
            </CardTitle>
            <CardDescription>
              Metadata and provenance for the entity currently anchoring the graph.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {selectedEntity ? (
              <>
                <div>
                  <div className="text-xs uppercase text-muted-foreground">Name</div>
                  <div className="font-medium">{selectedEntity.name}</div>
                </div>
                <div>
                  <div className="text-xs uppercase text-muted-foreground">Namespace</div>
                  <div>{selectedEntity.namespace}</div>
                </div>
                {selectedJob && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Type</div>
                    <div>{selectedJob.type}</div>
                  </div>
                )}
                {selectedDataset && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Type</div>
                    <div>{selectedDataset.type}</div>
                  </div>
                )}
                {selectedJob?.latestRun && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Latest Run</div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">
                        {selectedJob.latestRun.state}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {selectedJob.latestRun.updatedAt &&
                          new Date(selectedJob.latestRun.updatedAt).toLocaleString()}
                      </span>
                    </div>
                  </div>
                )}
                {selectedDataset?.sourceName && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Source</div>
                    <div>{selectedDataset.sourceName}</div>
                  </div>
                )}
                {selectedDataset?.tags && selectedDataset.tags.length > 0 && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Tags</div>
                    <div className="flex flex-wrap gap-1">
                      {selectedDataset.tags.map((tag) => (
                        <Badge key={tag} variant="secondary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                {selectedJob?.context && Object.keys(selectedJob.context).length > 0 && (
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Context Facets</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(selectedJob.context).slice(0, 6).map((key) => (
                        <Badge key={key} variant="secondary">
                          {key}
                        </Badge>
                      ))}
                      {Object.keys(selectedJob.context).length > 6 && (
                        <Badge variant="outline">
                          +{Object.keys(selectedJob.context).length - 6}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="rounded-2xl border border-dashed px-4 py-6 text-center text-muted-foreground">
                Select a job or dataset to view its metadata.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
