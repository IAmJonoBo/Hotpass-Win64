import { useMemo } from 'react'
import { Sparkles, ArrowUpRight, MessageSquare } from 'lucide-react'
import type { ImportProfile } from '@/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface CellSpotlightProps {
  logs: string[]
  profile?: ImportProfile | null
  onOpenAssistant?: (message?: string) => void
  className?: string
}

interface SpotlightInfo {
  sheet?: string | null
  cell?: string | null
  rule?: string | null
  message: string
}

const CELL_PATTERNS: Array<RegExp> = [
  /Sheet\s+(?<sheet>[A-Za-z0-9 _-]+)[\s:,-]+(?:Cell|cell)\s+(?<cell>[A-Z]+\d+)/i,
  /(?<sheet>[A-Za-z0-9 _-]+)!?(?<cell>[A-Z]+\d+)\s+(?:auto[-\s]?fix|fixed|normalised|normalized)/i,
  /(Cell|cell)\s+(?<cell>[A-Z]+\d+)\s+(?:in|on)\s+(?<sheet>[A-Za-z0-9 _-]+)/i,
]

const RULE_PATTERN = /(rule|validator|check)[:\s]+(?<rule>[A-Za-z0-9_.-]+)/i

const normaliseSheetName = (value?: string | null) =>
  value ? value.trim().replace(/\s+/g, ' ') : undefined

export function CellSpotlight({ logs, profile, onOpenAssistant, className }: CellSpotlightProps) {
  const spotlight = useMemo<SpotlightInfo | null>(() => {
    if (!Array.isArray(logs) || logs.length === 0) return null
    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const entry = logs[index]
      if (typeof entry !== 'string' || entry.trim().length === 0) continue

      let matchSheet: string | null | undefined
      let matchCell: string | null | undefined

      for (const pattern of CELL_PATTERNS) {
        const match = pattern.exec(entry)
        if (match?.groups) {
          matchSheet = match.groups.sheet ? normaliseSheetName(match.groups.sheet) : matchSheet
          matchCell = match.groups.cell ? match.groups.cell.toUpperCase() : matchCell
        }
        if (matchSheet || matchCell) break
      }

      if (!matchSheet && !matchCell) continue

      const ruleMatch = RULE_PATTERN.exec(entry)
      const rule = ruleMatch?.groups?.rule ? ruleMatch.groups.rule : null

      return {
        sheet: matchSheet ?? null,
        cell: matchCell ?? null,
        rule,
        message: entry.trim(),
      }
    }
    return null
  }, [logs])

  const sheetProfile = useMemo(() => {
    if (!spotlight?.sheet || !profile) return null
    const targetSheet = spotlight.sheet.toLowerCase()
    return profile.sheets.find(sheet => (sheet.name ?? '').toLowerCase() === targetSheet) ?? null
  }, [profile, spotlight?.sheet])

  return (
    <Card className={cn('rounded-2xl border border-border/70 bg-card/90 shadow-sm', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
          Cell Spotlight
        </CardTitle>
        <CardDescription>
          Highlights the latest cell-level auto-fix emitted by the import pipeline.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        {!spotlight ? (
          <div className="rounded-xl border border-dashed border-border/60 bg-muted/30 px-3 py-4 text-muted-foreground">
            No cell corrections detected yet. Run the pipeline or enable verbose logging to capture auto-fix events.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-[11px] uppercase text-muted-foreground">
              {spotlight.sheet ? (
                <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide">
                  {spotlight.sheet}
                </Badge>
              ) : (
                <Badge variant="outline" className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide">
                  Sheet unknown
                </Badge>
              )}
              <span>Cell {spotlight.cell ?? '—'}</span>
              {spotlight.rule && (
                <span className="inline-flex items-center gap-1 text-primary">
                  <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                  Rule {spotlight.rule}
                </span>
              )}
            </div>

            <div className="rounded-xl border border-border/60 bg-background/90 p-3 font-mono text-[11px] leading-relaxed text-foreground shadow-inner">
              {spotlight.message}
            </div>

            {sheetProfile && (
              <div className="rounded-xl border border-border/60 bg-background/90 p-3 text-[11px] text-muted-foreground">
                <p className="font-semibold text-foreground">{sheetProfile.name}</p>
                <p>
                  {sheetProfile.columns.length} columns • {sheetProfile.rows.toLocaleString()} rows
                </p>
              </div>
            )}

            {onOpenAssistant && (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  onOpenAssistant(
                    `Summarise the latest auto-fix event${spotlight.sheet ? ` on sheet ${spotlight.sheet}` : ''}${
                      spotlight.cell ? ` at cell ${spotlight.cell}` : ''
                    }. Log entry: ${spotlight.message}`,
                  )
                }
                className="gap-2"
              >
                <MessageSquare className="h-3 w-3" />
                Ask assistant about this fix
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
