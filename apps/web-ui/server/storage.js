import path from 'path'
import { mkdir, readFile, writeFile } from 'fs/promises'

const DATA_ROOT = process.env.HOTPASS_STATE_ROOT || path.join(process.cwd(), '.hotpass', 'ui')

async function ensureParentDir(filePath) {
  const dir = path.dirname(filePath)
  await mkdir(dir, { recursive: true })
}

async function readJson(filePath, fallback) {
  try {
    const data = await readFile(filePath, 'utf8')
    return JSON.parse(data)
  } catch (error) {
    if (error.code === 'ENOENT') {
      return typeof fallback === 'function' ? fallback() : fallback
    }
    throw error
  }
}

async function writeJson(filePath, value) {
  await ensureParentDir(filePath)
  const payload = JSON.stringify(value, null, 2)
  await writeFile(filePath, payload, 'utf8')
  return value
}

export const paths = {
  hilApprovals: path.join(DATA_ROOT, 'hil', 'approvals.json'),
  hilAudit: path.join(DATA_ROOT, 'hil', 'audit-log.json'),
  activityLog: path.join(DATA_ROOT, 'activity', 'events.json'),
}

export async function readHilApprovals() {
  const raw = await readJson(paths.hilApprovals, () => ({}))
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw
  }
  return {}
}

export async function writeHilApprovals(data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Hil approvals payload must be an object')
  }
  return writeJson(paths.hilApprovals, data)
}

export async function readHilAudit() {
  const raw = await readJson(paths.hilAudit, () => [])
  return Array.isArray(raw) ? raw : []
}

export async function writeHilAudit(entries) {
  if (!Array.isArray(entries)) {
    throw new Error('Hil audit log must be an array')
  }
  return writeJson(paths.hilAudit, entries)
}

export async function readActivityLog() {
  const raw = await readJson(paths.activityLog, () => [])
  return Array.isArray(raw) ? raw : []
}

export async function appendActivityEvent(event) {
  const current = await readActivityLog()
  current.unshift(event)
  const trimmed = current.slice(0, Number.parseInt(process.env.HOTPASS_ACTIVITY_LIMIT ?? '200', 10))
  await writeJson(paths.activityLog, trimmed)
  return trimmed
}
