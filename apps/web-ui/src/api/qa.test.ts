import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchLatestQaSummary } from './qa'

describe('fetchLatestQaSummary', () => {
  const originalFetch = globalThis.fetch

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('returns transformed QA results when request succeeds', async () => {
    const payload = {
      summary: {
        timestamp: '2025-11-04T09:35:24.976826+00:00',
        results: [
          {
            checkpoint: 'reachout_organisation',
            status: 'passed',
            message: 'Validation passed',
          },
        ],
      },
      dataDocsPath: '/dist/quality-gates/qg2-data-quality/20251104T093524Z/data-docs/index.html',
    }
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(payload),
    } as unknown as Response
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    const result = await fetchLatestQaSummary()

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/qa/latest', expect.any(Object))
    expect(result.timestamp).toBe(payload.summary.timestamp)
    expect(result.dataDocsPath).toBe(payload.dataDocsPath)
    expect(result.results).toHaveLength(1)
    expect(result.results[0]).toMatchObject({
      check: 'reachout_organisation',
      status: 'passed',
      message: 'Validation passed',
    })
  })

  it('throws when the backend responds with a non-OK status', async () => {
    const mockResponse = { ok: false, status: 404, statusText: 'Not Found' } as unknown as Response
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(fetchLatestQaSummary()).rejects.toThrow('Not Found')
  })
})
