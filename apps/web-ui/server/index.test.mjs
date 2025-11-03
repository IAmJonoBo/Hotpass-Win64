import { mkdtemp, rm, writeFile } from 'fs/promises'
import os from 'os'
import path from 'path'
import request from 'supertest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const originalNodeEnv = process.env.NODE_ENV

const MANIFEST_YAML = `version: 2025-11-18
maintainer: Platform
review_cadence: quarterly
assets:
  - id: storage
    name: Storage Bucket
    type: filesystem
    location: ./data
    classification: confidential
    owner: Data
    custodian: Platform
    description: Core dataset storage
`

const STATUS_YAML = `requirements:
  - id: backend-service
    surface: backend
    description: Backend loader
    status: implemented
`

describe('GET /api/inventory', () => {
  let tempDir
  let manifestPath
  let statusPath
  let app
  let resetInventoryCache

  beforeEach(async () => {
    tempDir = await mkdtemp(path.join(os.tmpdir(), 'hotpass-inventory-'))
    manifestPath = path.join(tempDir, 'asset-register.yaml')
    statusPath = path.join(tempDir, 'feature-status.yaml')
    await writeFile(manifestPath, MANIFEST_YAML, 'utf8')
    await writeFile(statusPath, STATUS_YAML, 'utf8')

    process.env.HOTPASS_INVENTORY_PATH = manifestPath
    process.env.HOTPASS_INVENTORY_FEATURE_STATUS_PATH = statusPath
    process.env.HOTPASS_INVENTORY_CACHE_TTL = '0'
    process.env.NODE_ENV = 'test'

    vi.resetModules()
    const module = await import('./index.mjs')
    app = module.app
    resetInventoryCache = module.resetInventoryCache
    resetInventoryCache()
  })

  afterEach(async () => {
    resetInventoryCache?.()
    delete process.env.HOTPASS_INVENTORY_PATH
    delete process.env.HOTPASS_INVENTORY_FEATURE_STATUS_PATH
    delete process.env.HOTPASS_INVENTORY_CACHE_TTL
    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV
    } else {
      process.env.NODE_ENV = originalNodeEnv
    }
    vi.resetModules()
    if (tempDir) {
      await rm(tempDir, { recursive: true, force: true })
    }
  })

  it('returns normalised inventory snapshot', async () => {
    const response = await request(app).get('/api/inventory')

    expect(response.status).toBe(200)
    expect(response.body.manifest.version).toBe('2025-11-18')
    expect(response.body.summary.total).toBe(1)
    expect(response.body.assets).toHaveLength(1)
    expect(response.body.requirements[0].status).toBe('implemented')
  })

  it('returns 503 when manifest is missing', async () => {
    await rm(manifestPath, { force: true })
    resetInventoryCache()

    const response = await request(app).get('/api/inventory')

    expect(response.status).toBe(503)
    expect(response.body.error).toBe('Inventory manifest not found')
  })
})
