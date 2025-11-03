import { useQuery } from '@tanstack/react-query'
import { createRateLimiter } from '@/lib/security'
import type {
  InventoryAsset,
  InventoryRequirement,
  InventorySnapshot,
  InventorySummary,
} from '@/types/inventory'

const limiter = createRateLimiter(6, 30_000)

const parseInventoryError = async (response: Response) => {
  try {
    const payload = await response.clone().json()
    if (payload && typeof payload === 'object') {
      const message =
        (payload as { error?: unknown }).error ?? (payload as { message?: unknown }).message
      if (typeof message === 'string' && message.trim()) {
        return message
      }
      const details = (payload as { details?: { message?: unknown } }).details
      if (details && typeof details === 'object' && typeof details.message === 'string') {
        return details.message
      }
    }
  } catch {
    // fall through to status text/text body parsing
  }

  try {
    const text = await response.clone().text()
    if (text.trim()) {
      return text.trim()
    }
  } catch {
    // ignore text parsing errors
  }

  return response.statusText || 'Failed to fetch inventory'
}

const fetchWithLimiter = <T>(input: RequestInfo | URL, init?: RequestInit) =>
  limiter(async () => {
    const response = await fetch(input, {
      credentials: 'include',
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
    })
    if (!response.ok) {
      const message = await parseInventoryError(response)
      throw new Error(message)
    }
    return response.json() as Promise<T>
  })

const normaliseAsset = (raw: unknown): InventoryAsset | null => {
  if (!raw || typeof raw !== 'object') return null
  const payload = raw as Record<string, unknown>
  const toString = (value: unknown, fallback = '') =>
    value === undefined || value === null ? fallback : String(value)
  const toStringArray = (value: unknown) => {
    if (!value) return []
    if (Array.isArray(value)) {
      return Array.from(new Set(value.map(item => String(item))))
    }
    return [String(value)]
  }

  const id = toString(payload.id || payload.name, 'unknown')
  return {
    id,
    name: toString(payload.name, id),
    type: toString(payload.type, 'unknown'),
    classification: toString(payload.classification, 'unknown'),
    owner: toString(payload.owner, 'unknown'),
    custodian: toString(payload.custodian, ''),
    location: toString(payload.location, ''),
    description: toString(payload.description, ''),
    dependencies: toStringArray(payload.dependencies),
    controls: toStringArray(payload.controls),
  }
}

const normaliseRequirements = (raw: unknown): InventoryRequirement[] => {
  if (!Array.isArray(raw)) return []
  return raw
    .map(item => {
      if (!item || typeof item !== 'object') return null
      const payload = item as Record<string, unknown>
      return {
        id: String(payload.id ?? 'unknown'),
        surface: String(payload.surface ?? 'unknown'),
        description: String(payload.description ?? ''),
        status: String(payload.status ?? 'planned'),
        detail:
          payload.detail === undefined || payload.detail === null
            ? null
            : String(payload.detail),
      } satisfies InventoryRequirement
    })
    .filter((item): item is InventoryRequirement => item !== null)
}

const normaliseSummary = (raw: unknown): InventorySummary => {
  if (!raw || typeof raw !== 'object') {
    return { total: 0, byType: {}, byClassification: {} }
  }
  const payload = raw as Record<string, unknown>
  const coerceMap = (value: unknown) => {
    if (!value || typeof value !== 'object') return {}
    const entries = Object.entries(value as Record<string, unknown>)
    return entries.reduce<Record<string, number>>((acc, [key, count]) => {
      const parsed = Number(count)
      acc[key] = Number.isFinite(parsed) ? parsed : 0
      return acc
    }, {})
  }
  const total = Number(payload.total)
  return {
    total: Number.isFinite(total) ? total : 0,
    byType: coerceMap(payload.byType),
    byClassification: coerceMap(payload.byClassification),
  }
}

const normaliseSnapshot = (raw: unknown): InventorySnapshot => {
  if (!raw || typeof raw !== 'object') {
    return {
      manifest: { version: 'unknown', maintainer: 'unknown', reviewCadence: 'unknown' },
      summary: { total: 0, byType: {}, byClassification: {} },
      requirements: [],
      assets: [],
      generatedAt: new Date(0).toISOString(),
    }
  }
  const payload = raw as Record<string, unknown>
  const manifestRaw = (payload.manifest as Record<string, unknown>) ?? {}
  const manifest = {
    version: String(manifestRaw.version ?? 'unknown'),
    maintainer: String(manifestRaw.maintainer ?? 'unknown'),
    reviewCadence: String(manifestRaw.reviewCadence ?? manifestRaw.review_cadence ?? 'unknown'),
  }

  const assets = Array.isArray(payload.assets)
    ? payload.assets
        .map(normaliseAsset)
        .filter((asset): asset is InventoryAsset => asset !== null)
    : []

  const generatedAt = String(payload.generatedAt ?? new Date().toISOString())

  return {
    manifest,
    summary: normaliseSummary(payload.summary),
    requirements: normaliseRequirements(payload.requirements),
    assets,
    generatedAt,
  }
}

export async function fetchInventory(): Promise<InventorySnapshot> {
  const payload = await fetchWithLimiter<unknown>('/api/inventory')
  return normaliseSnapshot(payload)
}

export function useInventory() {
  return useQuery({
    queryKey: ['inventory'],
    queryFn: fetchInventory,
    staleTime: 60_000,
  })
}

export { normaliseSnapshot }
