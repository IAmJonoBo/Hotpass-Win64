import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Database, FileJson, MapPin, Network, RefreshCw, Target, Notebook } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiBanner } from '@/components/feedback/ApiBanner'
import { cn } from '@/lib/utils'
import { useResearchMetadata } from '@/api/research'
import type { ResearchRecord, ResearchPlanStep } from '@/types'

const formatStepStatus = (status: string) => {
  const normalised = status.toLowerCase()
  if (normalised.includes('success')) return 'success'
  if (normalised.includes('fail')) return 'error'
  if (normalised.includes('skip')) return 'muted'
  return 'neutral'
}

const StepStatusBadge = ({ status }: { status: string }) => {
  const variant = formatStepStatus(status)
  const classes =
    variant === 'success'
      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300'
      : variant === 'error'
        ? 'bg-red-500/10 text-red-600 dark:text-red-400'
        : variant === 'muted'
          ? 'bg-muted/60 text-muted-foreground'
          : 'bg-primary/10 text-primary'
  return (
    <Badge variant="outline" className={cn('text-[10px] uppercase tracking-wide', classes)}>
      {status}
    </Badge>
  )
}

const downloadJson = (payload: unknown, filename: string) => {
  if (!payload) return
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  setTimeout(() => URL.revokeObjectURL(url), 1_000)
}

interface ResearchPlannerCardProps {
  onOpenAssistant?: (message: string) => void
}

export function ResearchPlannerCard({ onOpenAssistant }: ResearchPlannerCardProps) {
  const { data: records = [], isLoading, isError, error, refetch, isFetching } = useResearchMetadata()
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!selectedSlug && records.length > 0) {
      setSelectedSlug(records[0].slug)
    }
  }, [records, selectedSlug])

  const filteredRecords = useMemo(() => {
    if (!filter.trim()) return records
    const query = filter.trim().toLowerCase()
    return records.filter((record) => {
      const fields = [
        record.slug,
        record.entityName,
        record.priority ?? '',
        record.plan?.plan?.entity_slug ?? '',
      ]
      return fields.some(value => value?.toLowerCase().includes(query))
    })
  }, [records, filter])

  useEffect(() => {
    if (!selectedSlug && filteredRecords.length > 0) {
      setSelectedSlug(filteredRecords[0].slug)
    } else if (selectedSlug && filteredRecords.length > 0) {
      const exists = filteredRecords.some(record => record.slug === selectedSlug)
      if (!exists) {
        setSelectedSlug(filteredRecords[0].slug)
      }
    }
  }, [filteredRecords, selectedSlug])

  const selected: ResearchRecord | null =
    (selectedSlug && records.find(record => record.slug === selectedSlug)) ?? null

  const planSteps: ResearchPlanStep[] = selected?.plan?.steps ?? []
  const backfillFields = selected?.plan?.plan?.backfill_fields ?? []
  const targetUrls = selected?.plan?.plan?.target_urls ?? []

  return (
    <Card className="h-full">
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <MapPin className="h-4 w-4" />
              Research Planner
            </CardTitle>
            <CardDescription>
              Review offline research plans and site manifests before enabling network enrichments.
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={cn('mr-2 h-3 w-3', isFetching && 'animate-spin')} />
            Refresh
          </Button>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Filter by company, slug, or priority…"
            className="max-w-sm text-sm"
            aria-label="Filter research records"
          />
          <span className="text-xs text-muted-foreground">
            {filteredRecords.length} of {records.length} records
          </span>
        </div>
        {isError && error instanceof Error && (
          <ApiBanner
            variant="error"
            title="Unable to load research metadata"
            description={error.message}
          />
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : filteredRecords.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            No research manifests found under <code className="font-mono">docs/research</code>.
            Generate plans via Docs Refresh or the Assistant to populate this list.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs font-semibold uppercase text-muted-foreground">
                Entity
              </label>
              <select
                value={selectedSlug ?? ''}
                onChange={(event) => setSelectedSlug(event.target.value || null)}
                className="rounded-lg border border-border/60 bg-background px-3 py-2 text-sm"
              >
                {filteredRecords.map((record) => (
                  <option key={record.slug} value={record.slug}>
                    {record.entityName} ({record.slug})
                  </option>
                ))}
              </select>
              {selected?.priority && (
                <Badge variant="outline" className="uppercase">
                  Priority: {selected.priority}
                </Badge>
              )}
              {selected?.plan?.plan?.allow_network ? (
                <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-300">
                  <Network className="mr-1 h-3 w-3" />
                  Network allowed
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-300">
                  <AlertTriangle className="mr-1 h-3 w-3" />
                  Offline only
                </Badge>
              )}
            </div>

            {selected && (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-border/60 p-3 text-sm">
                    <div className="flex items-center gap-2 text-xs uppercase text-muted-foreground">
                      <Target className="h-3.5 w-3.5" />
                      Backfill targets
                    </div>
                    {backfillFields.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-sm">
                        {backfillFields.map(field => (
                          <li key={field} className="flex items-center gap-2">
                            <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                              {field}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-muted-foreground">No backfill slots defined.</p>
                    )}
                  </div>
                  <div className="rounded-xl border border-border/60 p-3 text-sm">
                    <div className="flex items-center gap-2 text-xs uppercase text-muted-foreground">
                      <Notebook className="h-3.5 w-3.5" />
                      Target URLs
                    </div>
                    {targetUrls.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-sm">
                        {targetUrls.map(url => (
                          <li key={url}>
                            <a href={url} className="text-primary hover:underline" target="_blank" rel="noreferrer">
                              {url}
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-muted-foreground">No URLs captured for this plan yet.</p>
                    )}
                  </div>
                </div>

                {planSteps.length > 0 && (
                  <div className="rounded-xl border border-border/60 p-3">
                    <div className="text-xs uppercase text-muted-foreground mb-2">Plan steps</div>
                    <div className="space-y-2">
                      {planSteps.map((step) => (
                        <div key={step.name} className="rounded-lg border border-border/50 px-3 py-2 text-sm">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{step.name}</span>
                            <StepStatusBadge status={step.status} />
                          </div>
                          {step.message && (
                            <p className="mt-1 text-xs text-muted-foreground">{step.message}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selected.manifest && (
                  <div className="rounded-xl border border-border/60 p-3 space-y-3">
                    <div className="flex items-center gap-2 text-xs uppercase text-muted-foreground">
                      <Database className="h-3.5 w-3.5" />
                      Site manifest
                    </div>
                    <div className="grid gap-2 text-sm md:grid-cols-2">
                      <div>
                        <span className="font-medium">Discovery status:</span>{' '}
                        <span className="text-muted-foreground">
                          {selected.manifest.discovery_status ?? 'pending'}
                        </span>
                      </div>
                      <div>
                        <span className="font-medium">Base URL:</span>{' '}
                        {selected.manifest.base_url ? (
                          <a
                            href={selected.manifest.base_url}
                            className="text-primary hover:underline"
                            target="_blank"
                            rel="noreferrer"
                          >
                            {selected.manifest.base_url}
                          </a>
                        ) : (
                          <span className="text-muted-foreground">not captured</span>
                        )}
                      </div>
                    </div>
                    {Array.isArray(selected.manifest.candidate_pages) && selected.manifest.candidate_pages.length > 0 && (
                      <div className="space-y-1 text-sm">
                        <div className="text-xs uppercase text-muted-foreground">Candidate pages</div>
                        <ul className="space-y-1">
                          {selected.manifest.candidate_pages.map((page, index) => (
                            <li key={`${page.url}-${index}`} className="rounded-lg border border-border/60 px-3 py-2 text-xs">
                              <div className="flex flex-wrap items-center gap-2">
                                <a href={page.url} className="text-primary hover:underline" target="_blank" rel="noreferrer">
                                  {page.url}
                                </a>
                                {page.category && (
                                  <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                                    {page.category}
                                  </Badge>
                                )}
                                {page.method && (
                                  <Badge variant="outline" className="text-[10px]">{page.method}</Badge>
                                )}
                              </div>
                              {page.notes && (
                                <p className="mt-1 text-muted-foreground">{page.notes}</p>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {Array.isArray(selected.manifest.notes) && selected.manifest.notes.length > 0 && (
                      <div className="space-y-1 text-sm">
                        <div className="text-xs uppercase text-muted-foreground">Notes</div>
                        <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                          {selected.manifest.notes.map((note, index) => (
                            <li key={`${selected.slug}-note-${index}`}>{note}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {selected.plan && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadJson(selected.plan, `${selected.slug}-plan.json`)}
                    >
                      <FileJson className="mr-2 h-3 w-3" />
                      Download plan JSON
                    </Button>
                  )}
                  {selected.manifest && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadJson(selected.manifest, `${selected.slug}-manifest.json`)}
                    >
                      <FileJson className="mr-2 h-3 w-3" />
                      Download manifest JSON
                    </Button>
                  )}
                  {onOpenAssistant && selected && (
                    <Button
                      size="sm"
                      onClick={() =>
                        onOpenAssistant(
                          `Plan research for entity ${selected.entityName} (slug=${selected.slug}) and summarise the outstanding backfill fields`,
                        )
                      }
                    >
                      Open in Assistant
                    </Button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
