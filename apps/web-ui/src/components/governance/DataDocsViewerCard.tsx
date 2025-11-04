import { useCallback, useEffect, useState } from 'react'
import { BookOpen, ExternalLink, Loader2, RefreshCw, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiBanner } from '@/components/feedback/ApiBanner'

interface DataDocsViewerCardProps {
  className?: string
}

export function DataDocsViewerCard({ className }: DataDocsViewerCardProps) {
  const [available, setAvailable] = useState<boolean | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [iframeKey, setIframeKey] = useState(0)

  const checkAvailability = useCallback(async () => {
    setChecking(true)
    setError(null)
    try {
      const response = await fetch('/data-docs/index.html', {
        method: 'HEAD',
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error(`Status ${response.status}`)
      }
      setAvailable(true)
    } catch (err) {
      console.warn('[data-docs] availability check failed', err)
      setAvailable(false)
      setError('Data Docs index not found. Run Docs Refresh to publish the latest validation artefacts.')
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    void checkAvailability()
  }, [checkAvailability])

  const handleRefresh = () => {
    setIframeKey((value) => value + 1)
    void checkAvailability()
  }

  return (
    <Card className={className}>
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="h-4 w-4" />
              Data Docs
            </CardTitle>
            <CardDescription>
              Preview the latest Great Expectations validation bundle exported to <code>dist/data-docs</code>.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleRefresh} disabled={checking}>
              <RefreshCw className={checking ? 'mr-2 h-3 w-3 animate-spin' : 'mr-2 h-3 w-3'} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild
              disabled={!available}
            >
              <a href="/data-docs/index.html" target="_blank" rel="noreferrer">
                <ExternalLink className="mr-2 h-3 w-3" />
                Open full view
              </a>
            </Button>
          </div>
        </div>
        {error && (
          <ApiBanner
            variant="warning"
            title="Data Docs unavailable"
            description={error}
            icon={AlertCircle}
          />
        )}
      </CardHeader>
      <CardContent>
        {checking && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground pb-3">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking Data Docs availability…
          </div>
        )}
        {available ? (
          <iframe
            key={iframeKey}
            src="/data-docs/index.html"
            title="Great Expectations Data Docs"
            className="h-80 w-full rounded-xl border border-border/60 bg-background"
          />
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
