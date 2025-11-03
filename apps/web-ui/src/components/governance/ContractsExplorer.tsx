import { useMemo } from 'react'
import { FileText, Download, RefreshCw, HelpCircle, MessageSquare } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useContracts } from '@/api/contracts'
import type { ContractSummary } from '@/api/contracts'
import { cn } from '@/lib/utils'

export interface ContractsExplorerProps {
  className?: string
  onOpenAssistant?: (message?: string) => void
  onOpenHelp?: (topicId?: string) => void
}

const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** index
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

const describeContract = (contract: ContractSummary) => {
  const profile = contract.profile || 'generic'
  const format = contract.format.toUpperCase()
  return `${profile} contract (${format}) updated ${new Date(contract.updatedAt).toLocaleString()}`
}

export function ContractsExplorer({ className, onOpenAssistant, onOpenHelp }: ContractsExplorerProps) {
  const contractsQuery = useContracts()
  const contracts = contractsQuery.data ?? []

  const topThree = useMemo(() => contracts.slice(0, 6), [contracts])

  return (
    <Card className={cn('rounded-3xl border border-border/80 bg-card/90 shadow-sm', className)}>
      <CardHeader className="flex flex-col gap-1 pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
              Contracts explorer
            </CardTitle>
            <CardDescription>
              Latest YAML/JSON contracts exported by the pipeline. Download and review before distribution.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Refresh"
              onClick={() => contractsQuery.refetch()}
              disabled={contractsQuery.isLoading}
            >
              <RefreshCw className={cn('h-4 w-4', contractsQuery.isRefetching && 'animate-spin')} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Open help"
              onClick={() => onOpenHelp?.('gov-data-handling')}
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-xs">
        {contractsQuery.isError ? (
          <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-600 dark:text-red-400">
            Unable to load contracts. {contractsQuery.error instanceof Error ? contractsQuery.error.message : 'Please retry shortly.'}
          </div>
        ) : contractsQuery.isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={`contract-skeleton-${index}`} className="h-16 w-full rounded-2xl" />
            ))}
          </div>
        ) : contracts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 p-4 text-muted-foreground">
            No contracts found under <code className="font-mono">dist/contracts</code>. Run the contracts emit command to generate artifacts.
          </div>
        ) : (
          <ul className="space-y-3">
            {topThree.map((contract) => (
              <li
                key={contract.id}
                className="rounded-2xl border border-border/60 bg-background/95 p-4 shadow-sm transition hover:border-primary/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-foreground" title={contract.name}>
                      {contract.name}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                      <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide">
                        {contract.format.toUpperCase()}
                      </Badge>
                      <span>{new Date(contract.updatedAt).toLocaleString()}</span>
                      <span>·</span>
                      <span>{formatBytes(contract.size)}</span>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <a href={contract.downloadUrl} download>
                      <Download className="mr-1 h-3 w-3" />
                      Download
                    </a>
                  </Button>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-2"
                    onClick={() =>
                      onOpenAssistant?.(
                        `Summarise the ${describeContract(contract)}. Filename: ${contract.name}.`,
                      )
                    }
                  >
                    <MessageSquare className="h-3 w-3" />
                    Ask assistant
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {contracts.length > topThree.length && (
          <div className="text-[11px] text-muted-foreground">
            Showing {topThree.length} of {contracts.length} contracts. Visit the contracts directory for additional files.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
