import { describe, expect, it } from 'vitest'

import { jobHasHotpassFacet, summariseLineageJobs } from './useLineageTelemetry'
import { mockMarquezData } from '@/api/marquez'

describe('summariseLineageJobs', () => {
  it('counts todays jobs and failures', () => {
    const today = new Date().toISOString()
    const jobs = [
      {
        ...mockMarquezData.jobs[0],
        latestRun: {
          ...mockMarquezData.jobs[0].latestRun!,
          createdAt: today,
          updatedAt: today,
          state: 'COMPLETED' as const,
          facets: { hotpass: {} },
        },
      },
      {
        ...mockMarquezData.jobs[1],
        latestRun: {
          ...mockMarquezData.jobs[1].latestRun!,
          createdAt: today,
          updatedAt: today,
          state: 'FAILED' as const,
          facets: {},
        },
      },
      {
        ...mockMarquezData.jobs[1],
        latestRun: undefined,
      },
    ]

    const summary = summariseLineageJobs(jobs)

    expect(summary.jobsToday).toBe(2)
    expect(summary.failedToday).toBe(1)
    expect(summary.incompleteFacets).toBe(2)
  })
})

describe('jobHasHotpassFacet', () => {
  it('detects hotpass facets irrespective of casing', () => {
    const job = {
      ...mockMarquezData.jobs[0],
      latestRun: {
        ...mockMarquezData.jobs[0].latestRun!,
        facets: {
          ExampleFacet: {},
          HOTPASS_Metadata: {},
        },
      },
    }

    expect(jobHasHotpassFacet(job)).toBe(true)
  })

  it('returns false when facets missing', () => {
    const job = { ...mockMarquezData.jobs[0], latestRun: undefined }
    expect(jobHasHotpassFacet(job)).toBe(false)
  })
})
