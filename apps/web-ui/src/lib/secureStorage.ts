import { openDB, type IDBPDatabase } from 'idb'
import type { HILApproval, HILAuditEntry } from '@/types'
import { getHilRetentionPolicy, applyRetentionPolicy } from './hilRetention'

interface EncryptedEnvelope {
  iv: string
  data: string
}

interface HilStore {
  approvals: Record<string, HILApproval>
  audit: HILAuditEntry[]
}

const DB_NAME = 'hotpass-hil-secure'
const DB_VERSION = 1
const APPROVALS_STORE = 'approvals'
const AUDIT_STORE = 'audit'

let dbPromise: Promise<IDBPDatabase> | null = null
let encryptionKey: CryptoKey | null = null
let activeUserId: string | null = null
const memoryFallback: Record<string, HilStore> = {}

const textEncoder = typeof TextEncoder !== 'undefined' ? new TextEncoder() : null
const textDecoder = typeof TextDecoder !== 'undefined' ? new TextDecoder() : null

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function fromBase64(value: string): ArrayBuffer {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

function getMemoryStore(): HilStore {
  const key = activeUserId ?? 'anonymous'
  if (!memoryFallback[key]) {
    memoryFallback[key] = { approvals: {}, audit: [] }
  }
  return memoryFallback[key]
}

async function getDb(): Promise<IDBPDatabase | null> {
  if (typeof window === 'undefined' || typeof indexedDB === 'undefined') {
    return null
  }
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(database) {
        if (!database.objectStoreNames.contains(APPROVALS_STORE)) {
          database.createObjectStore(APPROVALS_STORE)
        }
        if (!database.objectStoreNames.contains(AUDIT_STORE)) {
          database.createObjectStore(AUDIT_STORE)
        }
      },
    })
  }
  return dbPromise
}

async function encryptPayload(payload: unknown): Promise<EncryptedEnvelope | null> {
  if (!encryptionKey || !textEncoder || typeof window === 'undefined' || !window.crypto?.subtle) {
    return null
  }
  const iv = window.crypto.getRandomValues(new Uint8Array(12))
  const encoded = textEncoder.encode(JSON.stringify(payload))
  const cipher = await window.crypto.subtle.encrypt({ name: 'AES-GCM', iv }, encryptionKey, encoded)
  return { iv: toBase64(iv.buffer), data: toBase64(cipher) }
}

async function decryptPayload(envelope: EncryptedEnvelope): Promise<unknown> {
  if (!encryptionKey || !textDecoder || typeof window === 'undefined' || !window.crypto?.subtle) {
    return null
  }
  const iv = new Uint8Array(fromBase64(envelope.iv))
  const cipher = fromBase64(envelope.data)
  const decrypted = await window.crypto.subtle.decrypt({ name: 'AES-GCM', iv }, encryptionKey, cipher)
  return JSON.parse(textDecoder.decode(decrypted))
}

export function setHilSecurityContext({ userId, key }: { userId: string | null; key: CryptoKey | null }) {
  activeUserId = userId
  encryptionKey = key
}

export async function readApprovals(): Promise<Record<string, HILApproval>> {
  if (!activeUserId) {
    return {}
  }
  const db = await getDb()
  if (!db || !encryptionKey) {
    return getMemoryStore().approvals
  }
  const envelope = await db.get(APPROVALS_STORE, activeUserId)
  if (!envelope) {
    return {}
  }
  const payload = await decryptPayload(envelope)
  return (payload as Record<string, HILApproval>) ?? {}
}

export async function readAudit(): Promise<HILAuditEntry[]> {
  if (!activeUserId) {
    return []
  }
  const db = await getDb()
  if (!db || !encryptionKey) {
    return getMemoryStore().audit
  }
  const envelope = await db.get(AUDIT_STORE, activeUserId)
  if (!envelope) {
    return []
  }
  const payload = await decryptPayload(envelope)
  return Array.isArray(payload) ? (payload as HILAuditEntry[]) : []
}

export async function writeApprovals(approvals: Record<string, HILApproval>): Promise<void> {
  if (!activeUserId) {
    throw new Error('Secure storage not initialised for approvals')
  }
  const db = await getDb()
  if (!db || !encryptionKey) {
    getMemoryStore().approvals = approvals
    return
  }
  const envelope = await encryptPayload(approvals)
  if (!envelope) {
    throw new Error('Failed to encrypt approvals payload')
  }
  await db.put(APPROVALS_STORE, envelope, activeUserId)
}

export async function writeAudit(entries: HILAuditEntry[]): Promise<void> {
  if (!activeUserId) {
    throw new Error('Secure storage not initialised for audit trail')
  }
  const filtered = applyRetentionPolicy(entries)
  const db = await getDb()
  if (!db || !encryptionKey) {
    getMemoryStore().audit = filtered
    return
  }
  const envelope = await encryptPayload(filtered)
  if (!envelope) {
    throw new Error('Failed to encrypt audit payload')
  }
  await db.put(AUDIT_STORE, envelope, activeUserId)
}

export async function applyRetentionImmediately(): Promise<void> {
  if (!activeUserId) {
    return
  }
  const current = await readAudit()
  const filtered = applyRetentionPolicy(current)
  await writeAudit(filtered)
}

export function getRetentionPolicy() {
  return getHilRetentionPolicy()
}
