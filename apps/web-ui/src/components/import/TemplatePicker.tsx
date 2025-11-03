import { useMemo } from 'react'
import { Loader2, RefreshCw, Layers, Settings } from 'lucide-react'
import type { ImportTemplate } from '@/types'
import { useImportTemplates } from '@/api/imports'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface TemplatePickerProps {
  selectedTemplateId: string | null
  onSelect: (template: ImportTemplate | null) => void
  onManage?: () => void
}

export function TemplatePicker({ selectedTemplateId, onSelect, onManage }: TemplatePickerProps) {
  const {
    data: templates = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useImportTemplates()

  const selected = useMemo(
    () => templates.find(template => template.id === selectedTemplateId) ?? null,
    [templates, selectedTemplateId],
  )

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="flex items-center gap-2 text-base">
            <Layers className="h-4 w-4" />
            Templates
          </CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Pick a starting point for mappings and rules. Manage named templates via the forthcoming editor.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={cn('mr-2 h-3 w-3', isLoading && 'animate-spin')} />
            Refresh
          </Button>
          {onManage && (
            <Button variant="outline" size="sm" onClick={onManage}>
              <Settings className="mr-2 h-3 w-3" />
              Manage
            </Button>
          )}
          {selected && (
            <Button variant="ghost" size="sm" onClick={() => onSelect(null)}>
              Clear
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="flex items-center gap-2 rounded-2xl border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading templates…
          </div>
        ) : isError ? (
          <div className="space-y-2 rounded-2xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
            <p className="font-semibold">Unable to load templates</p>
            <p>{error instanceof Error ? error.message : 'Unknown error'}</p>
          </div>
        ) : templates.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/20 px-3 py-4 text-xs text-muted-foreground">
            No named templates yet. Attach profiles or promote a mapping to seed this list.
          </div>
        ) : (
          <div className="space-y-2">
            {templates.map(template => {
              const isSelected = template.id === selectedTemplateId
              return (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => onSelect(isSelected ? null : template)}
                  className={cn(
                    'w-full rounded-2xl border border-border/60 bg-card/80 px-3 py-3 text-left text-sm transition',
                    isSelected ? 'ring-2 ring-primary/60' : 'hover:bg-muted/60',
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-foreground">{template.name}</p>
                      {template.description && (
                        <p className="truncate text-xs text-muted-foreground">{template.description}</p>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {template.profile && (
                        <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                          {template.profile}
                        </Badge>
                      )}
                      {template.tags?.slice(0, 2).map(tag => (
                        <Badge key={`${template.id}-${tag}`} variant="outline" className="text-[10px]">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    Updated {new Date(template.updatedAt).toLocaleString()}
                  </p>
                </button>
              )
            })}
          </div>
        )}
        {selected && (
          <div className="rounded-2xl border border-border/60 bg-card/70 px-3 py-2 text-[11px] text-muted-foreground">
            <p className="font-semibold text-foreground">Selected template</p>
            <p>{selected.name}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
