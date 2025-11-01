import type { HILAuditEntry } from '@/types'

export interface HilRetentionPolicy {
  enabled: boolean
  days: number
}

const STORAGE_KEY = 'hotpass_hil_retention_policy'
const DEFAULT_POLICY: HilRetentionPolicy = {
  enabled: true,
  days: 30,
}

export function getHilRetentionPolicy(): HilRetentionPolicy {
  if (typeof window === 'undefined') {
    return DEFAULT_POLICY
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) {
      return DEFAULT_POLICY
    }
    const parsed = JSON.parse(stored) as Partial<HilRetentionPolicy>
    if (typeof parsed.days === 'number' && typeof parsed.enabled === 'boolean') {
      return { enabled: parsed.enabled, days: Math.max(1, parsed.days) }
    }
    return DEFAULT_POLICY
  } catch (error) {
    console.warn('Failed to read HIL retention policy', error)
    return DEFAULT_POLICY
  }
}

export function setHilRetentionPolicy(policy: HilRetentionPolicy) {
  if (typeof window === 'undefined') {
    return
  }
  const nextPolicy: HilRetentionPolicy = {
    enabled: policy.enabled,
    days: Math.max(1, Math.floor(policy.days)),
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextPolicy))
}

export function applyRetentionPolicy(entries: HILAuditEntry[]): HILAuditEntry[] {
  const policy = getHilRetentionPolicy()
  if (!policy.enabled) {
    return entries
  }
  const now = Date.now()
  const windowMs = policy.days * 24 * 60 * 60 * 1000
  return entries.filter(entry => {
    const timestamp = new Date(entry.timestamp).getTime()
    return Number.isFinite(timestamp) && now - timestamp <= windowMs
  })
}
