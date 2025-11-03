import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchInventory, normaliseSnapshot } from './inventory'

describe('inventory api', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('normalises snapshot payloads with defaults', () => {
    const payload = {
      manifest: { version: '1.0.0', maintainer: 'Ops', reviewCadence: 'quarterly' },
      summary: { total: 2, byType: { database: 1, secret: 1 }, byClassification: { sensitive: 1, internal: 1 } },
      requirements: [
        { id: 'backend', surface: 'backend', description: 'Backend ready', status: 'implemented', detail: null },
      ],
      assets: [
        {
          id: 'one',
          name: 'First asset',
          type: 'database',
          classification: 'sensitive',
          owner: 'Security',
          custodian: 'Platform',
          location: '/data',
          description: 'Test',
          dependencies: ['vault'],
          controls: ['encryption'],
        },
      ],
      generatedAt: '2025-01-01T00:00:00Z',
    }

    const snapshot = normaliseSnapshot(payload)
    expect(snapshot.manifest).toEqual({
      version: '1.0.0',
      maintainer: 'Ops',
      reviewCadence: 'quarterly',
    })
    expect(snapshot.summary.total).toBe(2)
    expect(snapshot.summary.byType.database).toBe(1)
    expect(snapshot.assets[0].name).toBe('First asset')
    expect(snapshot.requirements[0].status).toBe('implemented')
    expect(snapshot.generatedAt).toBe('2025-01-01T00:00:00Z')
  })

  it('fetchInventory uses fetch and normalises payload', async () => {
    const mockResponse = {
      manifest: { version: '1', maintainer: 'Ops', reviewCadence: 'monthly' },
      summary: { total: 1, byType: { secret: 1 }, byClassification: { confidential: 1 } },
      requirements: [],
      assets: [
        {
          id: 'secret-store',
          name: 'Secret Store',
          type: 'secret',
          classification: 'confidential',
          owner: 'Security',
          custodian: 'Platform',
          location: 'vault://secret',
        },
      ],
      generatedAt: '2025-02-02T00:00:00Z',
    }

    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        statusText: 'OK',
        json: () => Promise.resolve(mockResponse),
      }),
    ) as unknown as typeof fetch

    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchInventory()
    expect(fetchMock).toHaveBeenCalledWith('/api/inventory', expect.any(Object))
    expect(result.assets).toHaveLength(1)
    expect(result.manifest.version).toBe('1')
  })

  it('throws descriptive error when server responds with JSON error payload', async () => {
    const errorResponse = {
      error: 'Inventory manifest not found',
      details: { message: 'Inventory manifest not found at /data/inventory/asset-register.yaml' },
    }

    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: false,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve(errorResponse),
        text: () => Promise.resolve(''),
        clone: () => ({
          json: () => Promise.resolve(errorResponse),
          text: () => Promise.resolve(''),
        }),
      }),
    ) as unknown as typeof fetch

    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInventory()).rejects.toThrow('Inventory manifest not found')
    expect(fetchMock).toHaveBeenCalled()
  })
})
