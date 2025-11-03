import { useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { InventoryAsset, InventoryRequirement, InventorySnapshot } from '@/types/inventory'

interface InventoryOverviewProps {
  snapshot: InventorySnapshot | null
  isLoading?: boolean
  error?: string | null
  onRetry?: () => void
}

const statusVariant = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
  const normalised = status.toLowerCase()
  if (normalised === 'implemented') return 'default'
  if (normalised === 'planned') return 'secondary'
  if (normalised === 'degraded' || normalised === 'missing') return 'destructive'
  return 'outline'
}

const filterAssets = (assets: InventoryAsset[], query: string, classification: string) => {
  const search = query.trim().toLowerCase()
  return assets.filter(asset => {
    const matchesClassification =
      classification === 'all' ||
      asset.classification.toLowerCase() === classification.toLowerCase()
    if (!matchesClassification) return false
    if (!search) return true
    return (
      asset.name.toLowerCase().includes(search) ||
      asset.owner.toLowerCase().includes(search) ||
      asset.custodian.toLowerCase().includes(search) ||
      asset.location.toLowerCase().includes(search) ||
      asset.type.toLowerCase().includes(search)
    )
  })
}

export function InventoryOverview({ snapshot, isLoading = false, error, onRetry }: InventoryOverviewProps) {
  const [query, setQuery] = useState('')
  const [classificationFilter, setClassificationFilter] = useState('all')

  const manifest = snapshot?.manifest ?? {
    version: 'unknown',
    maintainer: 'unknown',
    reviewCadence: 'unknown',
  }
  const summary = snapshot?.summary ?? { total: 0, byType: {}, byClassification: {} }
  const requirements: InventoryRequirement[] = snapshot?.requirements ?? []
  const assets: InventoryAsset[] = snapshot?.assets ?? []

  const classifications = useMemo(() => {
    const unique = new Map<string, string>()
    for (const asset of assets) {
      const key = asset.classification.toLowerCase()
      if (!unique.has(key)) {
        unique.set(key, asset.classification)
      }
    }
    return ['all', ...Array.from(unique.values()).sort((a, b) => a.localeCompare(b))]
  }, [assets])

  const filteredAssets = useMemo(
    () => filterAssets(assets, query, classificationFilter),
    [assets, query, classificationFilter],
  )

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Card className="border-destructive/60 bg-destructive/10">
        <CardHeader>
          <CardTitle>Unable to load inventory</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        {onRetry && (
          <CardContent>
            <Button onClick={onRetry}>Retry</Button>
          </CardContent>
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Total assets</CardTitle>
            <CardDescription>{manifest.reviewCadence} review cadence</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold">{summary.total}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Maintainer: {manifest.maintainer} · Version: {manifest.version}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>By type</CardTitle>
            <CardDescription>Asset distribution by storage or service type</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(summary.byType).length === 0 && (
              <p className="text-sm text-muted-foreground">No types recorded.</p>
            )}
            {Object.entries(summary.byType).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between text-sm">
                <span className="font-medium capitalize">{type}</span>
                <span>{count}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>By classification</CardTitle>
            <CardDescription>Sensitivity and governance categories</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(summary.byClassification).length === 0 && (
              <p className="text-sm text-muted-foreground">No classifications recorded.</p>
            )}
            {Object.entries(summary.byClassification).map(([classification, count]) => (
              <div key={classification} className="flex items-center justify-between text-sm">
                <span className="font-medium capitalize">{classification}</span>
                <span>{count}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Feature implementation status</CardTitle>
          <CardDescription>Backend, CLI, and UI readiness for the inventory feature</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {requirements.length === 0 && (
            <p className="text-sm text-muted-foreground">No requirement data available.</p>
          )}
          {requirements.map(requirement => (
            <div
              key={`${requirement.surface}-${requirement.id}`}
              className="flex flex-col gap-1 rounded-xl border bg-muted/30 p-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <p className="text-sm font-medium capitalize">{requirement.surface}</p>
                <p className="text-xs text-muted-foreground">{requirement.description}</p>
                {requirement.detail && (
                  <p className="mt-1 text-xs text-muted-foreground">{requirement.detail}</p>
                )}
              </div>
              <Badge variant={statusVariant(requirement.status)} className="w-fit uppercase">
                {requirement.status}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle>Asset inventory</CardTitle>
            <CardDescription>Search and filter the governed asset register</CardDescription>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Input
              type="search"
              placeholder="Search by name, owner, custodian, or type"
              value={query}
              onChange={event => setQuery(event.target.value)}
              className="w-full min-w-[220px]"
            />
            <select
              aria-label="Filter by classification"
              className="min-w-[180px] rounded-lg border bg-background px-3 py-2 text-sm"
              value={classificationFilter}
              onChange={event => setClassificationFilter(event.target.value)}
            >
              {classifications.map(classification => (
                <option key={classification} value={classification}>
                  {classification === 'all' ? 'All classifications' : classification}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {filteredAssets.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No assets match the selected filters. Try adjusting your search or classification.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Classification</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Custodian</TableHead>
                  <TableHead>Location</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAssets.map(asset => (
                  <TableRow key={asset.id}>
                    <TableCell className="font-mono text-xs">{asset.id}</TableCell>
                    <TableCell className="font-medium">{asset.name}</TableCell>
                    <TableCell>{asset.type}</TableCell>
                    <TableCell className="capitalize">{asset.classification}</TableCell>
                    <TableCell>{asset.owner}</TableCell>
                    <TableCell>{asset.custodian || '—'}</TableCell>
                    <TableCell>{asset.location || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
