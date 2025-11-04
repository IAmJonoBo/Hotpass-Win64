import path from 'path'
import crypto from 'crypto'
import { mkdir, readFile, writeFile, readdir, rm, stat } from 'fs/promises'

const DATA_ROOT = process.env.HOTPASS_STATE_ROOT || path.join(process.cwd(), '.hotpass', 'ui')
const IMPORT_PROFILES_DIR = path.join(DATA_ROOT, 'imports', 'profiles')
const IMPORT_TEMPLATES_DIR = path.join(DATA_ROOT, 'imports', 'templates')
const RESEARCH_ROOT = process.env.HOTPASS_RESEARCH_ROOT || path.join(process.cwd(), 'docs', 'research')

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

const ensureImportDirs = async () => {
  await mkdir(IMPORT_PROFILES_DIR, { recursive: true })
  await mkdir(IMPORT_TEMPLATES_DIR, { recursive: true })
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

const dedupeTags = (input) => {
  if (!Array.isArray(input)) return []
  return Array.from(new Set(input.map(tag => String(tag).trim()).filter(Boolean)))
}

const normaliseTemplateName = (name) => {
  const trimmed = String(name ?? '').trim()
  if (!trimmed) {
    throw new Error('Template name is required')
  }
  return trimmed
}

const generateId = (prefix) => `${prefix}-${crypto.randomUUID?.() ?? Math.random().toString(16).slice(2)}`

async function readDirectoryJsonEntries(dir, parser) {
  const entries = []
  try {
    const filenames = await readdir(dir)
    for (const filename of filenames) {
      if (!filename.endsWith('.json')) continue
      const filePath = path.join(dir, filename)
      try {
        const payload = await readJson(filePath, null)
        if (payload) {
          entries.push(parser(payload, filename.replace(/\.json$/, '')))
        }
      } catch (error) {
        console.warn(`[storage] failed to read ${filePath}`, error)
      }
    }
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error
    }
  }
  return entries
}

// Import profiles

export async function listImportProfiles() {
  await ensureImportDirs()
  const entries = await readDirectoryJsonEntries(IMPORT_PROFILES_DIR, (payload, id) => {
    if (payload && typeof payload === 'object') {
      return {
        id: payload.id ?? id,
        createdAt: payload.createdAt ?? new Date().toISOString(),
        source: payload.source ?? 'upload',
        workbookPath: payload.workbookPath,
        tags: Array.isArray(payload.tags) ? payload.tags : [],
        description: typeof payload.description === 'string' ? payload.description : undefined,
        profile: payload.profile ?? null,
      }
    }
    return null
  })
  return entries
    .filter(Boolean)
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
}

export async function readImportProfile(profileId) {
  await ensureImportDirs()
  const filePath = path.join(IMPORT_PROFILES_DIR, `${profileId}.json`)
  const payload = await readJson(filePath, null)
  return payload
}

export async function writeImportProfile(entry) {
  await ensureImportDirs()
  const id = entry.id ?? generateId('profile')
  const now = new Date().toISOString()
  const persisted = {
    ...entry,
    id,
    createdAt: entry.createdAt ?? now,
    updatedAt: now,
    tags: dedupeTags(entry.tags),
  }
  const filePath = path.join(IMPORT_PROFILES_DIR, `${id}.json`)
  await writeJson(filePath, persisted)
  return persisted
}

export async function deleteImportProfile(profileId) {
  await ensureImportDirs()
  const filePath = path.join(IMPORT_PROFILES_DIR, `${profileId}.json`)
  try {
    await rm(filePath, { force: true })
    return true
  } catch (error) {
    if (error.code === 'ENOENT') {
      return false
    }
    throw error
  }
}

// Import templates

export async function listImportTemplates() {
  await ensureImportDirs()
  const entries = await readDirectoryJsonEntries(IMPORT_TEMPLATES_DIR, (payload, id) => {
    if (payload && typeof payload === 'object') {
      return {
        id: payload.id ?? id,
        name: normaliseTemplateName(payload.name ?? id),
        description: typeof payload.description === 'string' ? payload.description : undefined,
        profile: typeof payload.profile === 'string' ? payload.profile : undefined,
        tags: Array.isArray(payload.tags) ? payload.tags : [],
        createdAt: payload.createdAt ?? new Date().toISOString(),
        updatedAt: payload.updatedAt ?? new Date().toISOString(),
        payload: payload.payload ?? {},
      }
    }
    return null
  })
  return entries.filter(Boolean).sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
}

export async function readImportTemplate(templateId) {
  await ensureImportDirs()
  const filePath = path.join(IMPORT_TEMPLATES_DIR, `${templateId}.json`)
  return readJson(filePath, null)
}

export async function getImportTemplatePath(templateId) {
  await ensureImportDirs()
  return path.join(IMPORT_TEMPLATES_DIR, `${templateId}.json`)
}

export async function writeImportTemplate(input) {
  await ensureImportDirs()
  const id = input.id ?? generateId('template')
  const now = new Date().toISOString()
  let createdAt = input.createdAt

  if (!createdAt) {
    try {
      const existing = await readJson(path.join(IMPORT_TEMPLATES_DIR, `${id}.json`), null)
      if (existing?.createdAt) {
        createdAt = existing.createdAt
      }
    } catch {
      // ignore
    }
  }

  const payload = {
    ...input,
    id,
    name: normaliseTemplateName(input.name),
    tags: dedupeTags(input.tags),
    createdAt: createdAt ?? now,
    updatedAt: now,
    payload: input.payload ?? {},
  }

  const filePath = path.join(IMPORT_TEMPLATES_DIR, `${id}.json`)
  await writeJson(filePath, payload)
  return payload
}

export async function deleteImportTemplate(templateId) {
  await ensureImportDirs()
  const filePath = path.join(IMPORT_TEMPLATES_DIR, `${templateId}.json`)
  try {
    await rm(filePath, { force: true })
    return true
  } catch (error) {
    if (error.code === 'ENOENT') {
      return false
    }
    throw error
  }
}

export async function touchImportTemplate(templateId) {
  await ensureImportDirs()
  const filePath = path.join(IMPORT_TEMPLATES_DIR, `${templateId}.json`)
  try {
    await stat(filePath)
    const existing = await readJson(filePath, null)
    if (existing) {
      existing.updatedAt = new Date().toISOString()
      await writeJson(filePath, existing)
      return true
    }
  } catch (error) {
    if (error.code === 'ENOENT') {
      return false
    }
    throw error
  }
  return false
}

async function readResearchJson(filePath) {
  try {
    const payload = await readJson(filePath, null)
    return payload && typeof payload === 'object' ? payload : null
  } catch (error) {
    console.warn('[storage] failed to read research JSON', filePath, error)
    return null
  }
}

export async function listResearchMetadata() {
  let dirEntries = []
  try {
    dirEntries = await readdir(RESEARCH_ROOT, { withFileTypes: true })
  } catch (error) {
    if (error.code === 'ENOENT') {
      return []
    }
    throw error
  }

  const records = []
  for (const entry of dirEntries) {
    if (!entry.isDirectory()) continue
    const slug = entry.name
    const planPath = path.join(RESEARCH_ROOT, slug, 'plan.json')
    const manifestPath = path.join(RESEARCH_ROOT, slug, 'site_manifest.json')
    const plan = await readResearchJson(planPath)
    const manifest = await readResearchJson(manifestPath)
    if (!plan && !manifest) continue

    const entityName =
      plan?.plan?.entity_name ??
      manifest?.entity_name ??
      slug
    const generatedAt =
      manifest?.generated_at ??
      plan?.plan?.generated_at ??
      plan?.generated_at ??
      null
    const priority =
      manifest?.priority ??
      plan?.plan?.priority ??
      null

    records.push({
      slug,
      entityName,
      generatedAt,
      priority,
      plan: plan ?? null,
      manifest: manifest ?? null,
    })
  }

  return records.sort((a, b) => {
    const left = a.generatedAt ? new Date(a.generatedAt).getTime() : 0
    const right = b.generatedAt ? new Date(b.generatedAt).getTime() : 0
    if (right !== left) {
      return right - left
    }
    return a.slug.localeCompare(b.slug)
  })
}

export async function readResearchRecord(slug) {
  if (!slug) return null
  const planPath = path.join(RESEARCH_ROOT, slug, 'plan.json')
  const manifestPath = path.join(RESEARCH_ROOT, slug, 'site_manifest.json')
  const plan = await readResearchJson(planPath)
  const manifest = await readResearchJson(manifestPath)
  if (!plan && !manifest) {
    return null
  }

  return {
    slug,
    entityName:
      plan?.plan?.entity_name ??
      manifest?.entity_name ??
      slug,
    generatedAt:
      manifest?.generated_at ??
      plan?.plan?.generated_at ??
      plan?.generated_at ??
      null,
    priority:
      manifest?.priority ??
      plan?.plan?.priority ??
      null,
    plan: plan ?? null,
    manifest: manifest ?? null,
  }
}
