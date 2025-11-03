import type { ImportTemplate, ImportTemplatePayload } from '@/types'

export interface NormalisedMapping {
  source: string
  target: string
  defaultValue?: string
  transform?: string
  strip?: boolean
  drop?: boolean
}

export interface NormalisedRule {
  type: string
  columns: string[]
  config: Record<string, unknown>
}

export interface TemplateDiff {
  addedMappings: NormalisedMapping[]
  removedMappings: NormalisedMapping[]
  changedMappings: Array<{ before: NormalisedMapping; after: NormalisedMapping }>
  addedRules: NormalisedRule[]
  removedRules: NormalisedRule[]
  changedRules: Array<{ before: NormalisedRule; after: NormalisedRule }>
}

export interface TemplateSummary {
  mappingCount: number
  ruleCount: number
  transforms: string[]
  ruleTypes: string[]
  profile?: string
  tags?: string[]
}

const normaliseMapping = (mapping: Record<string, unknown>): NormalisedMapping => ({
  source: typeof mapping.source === 'string' ? mapping.source : '',
  target: typeof mapping.target === 'string' ? mapping.target : '',
  defaultValue: typeof mapping.default === 'string' ? mapping.default : undefined,
  transform: typeof mapping.transform === 'string' ? mapping.transform : undefined,
  strip: Boolean(mapping.strip),
  drop: Boolean(mapping.drop),
})

const normaliseRule = (rule: Record<string, unknown>): NormalisedRule => {
  const columnsRaw = Array.isArray(rule.columns)
    ? rule.columns.map(column => String(column))
    : typeof rule.columns === 'string'
      ? rule.columns.split(',').map(column => column.trim()).filter(Boolean)
      : []
  const { type, ...rest } = rule
  return {
    type: typeof type === 'string' ? type : '',
    columns: [...columnsRaw].sort((a, b) => a.localeCompare(b)),
    config: rest as Record<string, unknown>,
  }
}

export const normaliseMappings = (payload: ImportTemplatePayload | null | undefined): NormalisedMapping[] => {
  if (!payload?.import_mappings || !Array.isArray(payload.import_mappings)) return []
  return payload.import_mappings.map(mapping =>
    normaliseMapping(mapping as Record<string, unknown>),
  )
}

export const normaliseRules = (payload: ImportTemplatePayload | null | undefined): NormalisedRule[] => {
  if (!payload?.import_rules || !Array.isArray(payload.import_rules)) return []
  return payload.import_rules.map(rule =>
    normaliseRule(rule as Record<string, unknown>),
  )
}

const buildMappingKey = (mapping: NormalisedMapping) =>
  `${mapping.source.toLowerCase()}→${mapping.target.toLowerCase()}`

const buildRuleKey = (rule: NormalisedRule) =>
  `${rule.type.toLowerCase()}::${rule.columns.join('|').toLowerCase()}`

export const buildTemplateDiff = (
  basePayload: ImportTemplatePayload | null | undefined,
  draftPayload: ImportTemplatePayload | null | undefined,
): TemplateDiff => {
  const baseMappings = normaliseMappings(basePayload)
  const draftMappings = normaliseMappings(draftPayload)
  const baseRules = normaliseRules(basePayload)
  const draftRules = normaliseRules(draftPayload)

  const baseMappingMap = new Map<string, NormalisedMapping>()
  baseMappings.forEach(mapping => baseMappingMap.set(buildMappingKey(mapping), mapping))
  const draftMappingMap = new Map<string, NormalisedMapping>()
  draftMappings.forEach(mapping => draftMappingMap.set(buildMappingKey(mapping), mapping))

  const addedMappings: NormalisedMapping[] = []
  const removedMappings: NormalisedMapping[] = []
  const changedMappings: Array<{ before: NormalisedMapping; after: NormalisedMapping }> = []

  draftMappingMap.forEach((mapping, key) => {
    const previous = baseMappingMap.get(key)
    if (!previous) {
      addedMappings.push(mapping)
    } else if (JSON.stringify(previous) !== JSON.stringify(mapping)) {
      changedMappings.push({ before: previous, after: mapping })
    }
  })

  baseMappingMap.forEach((mapping, key) => {
    if (!draftMappingMap.has(key)) {
      removedMappings.push(mapping)
    }
  })

  const baseRuleMap = new Map<string, NormalisedRule>()
  baseRules.forEach(rule => baseRuleMap.set(buildRuleKey(rule), rule))
  const draftRuleMap = new Map<string, NormalisedRule>()
  draftRules.forEach(rule => draftRuleMap.set(buildRuleKey(rule), rule))

  const addedRules: NormalisedRule[] = []
  const removedRules: NormalisedRule[] = []
  const changedRules: Array<{ before: NormalisedRule; after: NormalisedRule }> = []

  draftRuleMap.forEach((rule, key) => {
    const previous = baseRuleMap.get(key)
    if (!previous) {
      addedRules.push(rule)
    } else if (JSON.stringify(previous) !== JSON.stringify(rule)) {
      changedRules.push({ before: previous, after: rule })
    }
  })

  baseRuleMap.forEach((rule, key) => {
    if (!draftRuleMap.has(key)) {
      removedRules.push(rule)
    }
  })

  return {
    addedMappings,
    removedMappings,
    changedMappings,
    addedRules,
    removedRules,
    changedRules,
  }
}

export const summariseTemplate = (
  template: ImportTemplate | null | undefined,
  payload: ImportTemplatePayload | null | undefined = template?.payload,
): TemplateSummary => {
  const mappings = normaliseMappings(payload)
  const rules = normaliseRules(payload)
  const transforms = Array.from(
    new Set(mappings.map(mapping => mapping.transform).filter(Boolean) as string[]),
  )
  const ruleTypes = Array.from(new Set(rules.map(rule => rule.type).filter(Boolean)))
  return {
    mappingCount: mappings.length,
    ruleCount: rules.length,
    transforms,
    ruleTypes,
    profile: template?.profile,
    tags: template?.tags,
  }
}

export const buildTemplateContract = (options: {
  template: Pick<ImportTemplate, 'name' | 'profile' | 'description' | 'tags'>
  payload: ImportTemplatePayload
  origin?: string
}): Record<string, unknown> => {
  const mappings = normaliseMappings(options.payload)
  const rules = normaliseRules(options.payload)
  return {
    contract_version: '2025-11-03',
    generated_at: new Date().toISOString(),
    origin: options.origin ?? 'wizard',
    template: {
      name: options.template.name,
      profile: options.template.profile ?? 'generic',
      description: options.template.description ?? null,
      tags: options.template.tags ?? [],
    },
    mappings,
    rules,
  }
}

export const summariseConsolidation = (
  payload: ImportTemplatePayload | null | undefined,
): Record<string, unknown> => {
  const mappings = normaliseMappings(payload)
  const rules = normaliseRules(payload)
  const keyTargets = mappings
    .map(mapping => mapping.target)
    .filter(Boolean)
    .map(target => target.toLowerCase())
  const idColumns = keyTargets.filter(target => target.includes('id'))
  const contactColumns = keyTargets.filter(target => target.includes('contact'))
  return {
    mappingCount: mappings.length,
    ruleCount: rules.length,
    idColumns,
    contactColumns,
    ruleTypes: Array.from(new Set(rules.map(rule => rule.type).filter(Boolean))),
  }
}
