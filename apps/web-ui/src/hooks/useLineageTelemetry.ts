import { useQuery } from '@tanstack/react-query'
import { marquezApi } from '@/api/marquez'
import type { MarquezJob } from '@/types'

export interface LineageTelemetry {
  jobsToday: number
  failedToday: number
  incompleteFacets: number
  lastUpdated?: string
  jobs: MarquezJob[]
}

const DEFAULT_NAMESPACE = 'hotpass'

function isToday(dateString?: string): boolean {
  if (!dateString) return false
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return false
  const today = new Date()
  return (
    date.getUTCFullYear() === today.getUTCFullYear() &&
    date.getUTCMonth() === today.getUTCMonth() &&
    date.getUTCDate() === today.getUTCDate()
  )
}

export function jobHasHotpassFacet(job: MarquezJob): boolean {
  const facets = job?.latestRun?.facets
  if (!facets) return false
  return Object.keys(facets).some((key) => key.toLowerCase().includes('hotpass'))
}

export function summariseLineageJobs(jobs: MarquezJob[]) {
  let jobsToday = 0
  let failedToday = 0
  let incompleteFacets = 0

  for (const job of jobs) {
    const latestRun = job.latestRun
    if (latestRun) {
      if (isToday(latestRun.createdAt) || isToday(latestRun.updatedAt)) {
        jobsToday += 1
        if (latestRun.state === 'FAILED' || latestRun.state === 'ABORTED') {
          failedToday += 1
        }
      }
      if (!jobHasHotpassFacet(job)) {
        incompleteFacets += 1
      }
    } else {
      incompleteFacets += 1
    }
  }

  return {
    jobsToday,
    failedToday,
    incompleteFacets,
  }
}

export function useLineageTelemetry(namespace: string = DEFAULT_NAMESPACE) {
  return useQuery<LineageTelemetry>({
    queryKey: ['marquez-jobs', namespace],
    queryFn: async () => {
      const jobs = await marquezApi.getJobs(namespace, 200)
      const summary = summariseLineageJobs(jobs)

      return {
        ...summary,
        jobs,
        lastUpdated: new Date().toISOString(),
      }
    },
    staleTime: 60000,
    refetchInterval: 60000,
  })
}
