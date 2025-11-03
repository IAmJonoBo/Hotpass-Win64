import { describe, expect, it, afterEach, vi } from 'vitest'
import { fetchPipelineRuns } from './usePipelineRuns'

describe('fetchPipelineRuns', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    vi.resetAllMocks()
  })

  it('returns parsed pipeline runs when request succeeds', async () => {
    const payload = { runs: [{ id: '1', status: 'succeeded' }] }
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(payload),
    } as unknown as Response
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    const result = await fetchPipelineRuns(10)

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/runs/recent?limit=10',
      expect.objectContaining({
        credentials: 'include',
      }),
    )
    expect(result).toEqual(payload)
  })

  it('throws when the backend responds with a non-OK status', async () => {
    const mockResponse = { ok: false, status: 500 } as unknown as Response
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(fetchPipelineRuns(5)).rejects.toThrow('Failed to load recent runs (500)')
  })

  it('throws when the payload is not the expected shape', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue({}),
    } as unknown as Response
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(fetchPipelineRuns()).rejects.toThrow('Received an unexpected response for recent runs')
  })
})
