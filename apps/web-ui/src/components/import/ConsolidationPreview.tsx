import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const sections = [
  {
    id: 'master',
    title: 'Master entities',
    summary: 'Normalized company roster with golden records (deduped on source_id + organization_name).',
    stats: {
      columns: ['organization_name', 'source_id', 'industry', 'country'],
      enrichment: 'Deterministic',
    },
  },
  {
    id: 'contacts',
    title: 'Contacts',
    summary: 'Contact details linked to master entities with validation on email/phone.',
    stats: {
      columns: ['organization_name', 'contact_name', 'email', 'phone'],
      enrichment: 'HIL + enrichment optional',
    },
  },
  {
    id: 'addresses',
    title: 'Addresses',
    summary: 'Location roll-up for each entity, supporting multi-office footprints and geocodes.',
    stats: {
      columns: ['organization_name', 'address_line', 'city', 'country'],
      enrichment: 'Geospatial',
    },
  },
  {
    id: 'relations',
    title: 'Relationships',
    summary: 'Inter-entity relationships (parent/subsidiary, supplier, partner) for downstream graph analytics.',
    stats: {
      columns: ['source', 'target', 'relationship_type', 'confidence'],
      enrichment: 'Manual + orchestration',
    },
  },
] as const

export interface ConsolidationPreviewProps {
  profileName?: string | null
  mappingCount: number
  ruleCount: number
  onDownload?: () => void
}

export function ConsolidationPreview({
  profileName,
  mappingCount,
  ruleCount,
  onDownload,
}: ConsolidationPreviewProps) {
  const [activeSection, setActiveSection] = useState<(typeof sections)[number]['id']>('master')
  const currentSection = sections.find(section => section.id === activeSection) ?? sections[0]

  return (
    <div className="rounded-3xl border border-border/80 bg-card/90 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Consolidation preview</h2>
          <p className="text-[11px] text-muted-foreground">
            Profile <Badge variant="outline" className="ml-1 text-[10px] uppercase tracking-wide">{profileName || 'generic'}</Badge> · {mappingCount} mappings · {ruleCount} rules
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={onDownload} disabled={!onDownload}>
          Download sample preview
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {sections.map(section => (
          <button
            key={section.id}
            type="button"
            onClick={() => setActiveSection(section.id)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs font-medium transition',
              section.id === activeSection
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border/60 bg-muted/40 text-muted-foreground hover:bg-muted/60',
            )}
          >
            {section.title}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3 rounded-2xl border border-border/60 bg-background/80 p-4 text-xs">
        <p className="font-semibold text-foreground">{currentSection.title}</p>
        <p className="text-muted-foreground">{currentSection.summary}</p>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase text-muted-foreground">Key columns</p>
            <ul className="rounded-xl border border-border/60 bg-card/80 px-3 py-2">
              {currentSection.stats.columns.map(column => (
                <li key={column} className="text-xs text-foreground">{column}</li>
              ))}
            </ul>
          </div>
          <div className="space-y-1">
            <p className="text-[11px] font-semibold uppercase text-muted-foreground">Enrichment</p>
            <div className="rounded-xl border border-border/60 bg-card/80 px-3 py-2 text-xs text-foreground">
              {currentSection.stats.enrichment}
            </div>
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Verbose preview and diff tooling will attach here once consolidation pipelines ship.
        </p>
      </div>
    </div>
  )
}
