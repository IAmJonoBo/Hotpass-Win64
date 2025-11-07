import { BookOpenCheck, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const DEFAULT_GUIDE_URL = 'https://github.com/IAmJonoBo/Hotpass/blob/main/docs/how-to-guides/e2e-walkthrough.md'

export function E2EWalkthroughCard({ className }: { className?: string }) {
  const guideUrl =
    import.meta.env.VITE_E2E_GUIDE_URL ||
    import.meta.env.HOTPASS_E2E_GUIDE_URL ||
    '/docs/e2e-walkthrough.md'

  const resolvedUrl = guideUrl.startsWith('/') ? guideUrl : guideUrl || DEFAULT_GUIDE_URL

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpenCheck className="h-4 w-4" />
          E2E walkthrough
        </CardTitle>
        <CardDescription>
          Step-by-step instructions covering refinement, enrichment, QA gates, and Prefect orchestration.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-muted-foreground">
          Use this when onboarding operators or proving the stack works offline. The same flow mirrors the staging rehearsal
          so evidence stays portable.
        </p>
        <Button variant="outline" size="sm" asChild>
          <a href={resolvedUrl || DEFAULT_GUIDE_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="mr-2 h-3 w-3" />
            Open guide
          </a>
        </Button>
      </CardContent>
    </Card>
  )
}
