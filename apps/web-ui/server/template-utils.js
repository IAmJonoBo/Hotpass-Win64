import path from 'path'

const slugify = (value) => value
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '_')
  .replace(/_{2,}/g, '_')
  .replace(/^_|_$/g, '')

const normaliseMapping = (mapping = {}) => ({
  source: typeof mapping.source === 'string' ? mapping.source : '',
  target: typeof mapping.target === 'string' ? mapping.target : '',
  defaultValue: typeof mapping.default === 'string' ? mapping.default : undefined,
  transform: typeof mapping.transform === 'string' ? mapping.transform : undefined,
  strip: Boolean(mapping.strip),
  drop: Boolean(mapping.drop),
})

const normaliseRule = (rule = {}) => {
  const rawColumns = Array.isArray(rule.columns)
    ? rule.columns.map(column => String(column))
    : typeof rule.columns === 'string'
      ? rule.columns.split(',').map(column => column.trim()).filter(Boolean)
      : []
  const { type, columns, ...rest } = rule
  const config = { ...rest }
  return {
    type: typeof type === 'string' ? type : '',
    columns: rawColumns.sort((a, b) => a.localeCompare(b)),
    config,
  }
}

export const normaliseMappings = (payload) => {
  if (!payload || !Array.isArray(payload.import_mappings)) return []
  return payload.import_mappings.map(mapping => normaliseMapping(mapping))
}

export const normaliseRules = (payload) => {
  if (!payload || !Array.isArray(payload.import_rules)) return []
  return payload.import_rules.map(rule => normaliseRule(rule))
}

export const summariseTemplate = (template = {}, payload = template.payload) => {
  const mappings = normaliseMappings(payload)
  const rules = normaliseRules(payload)
  const transforms = Array.from(
    new Set(mappings.map(mapping => mapping.transform).filter(Boolean)),
  )
  const ruleTypes = Array.from(new Set(rules.map(rule => rule.type).filter(Boolean)))
  return {
    mappingCount: mappings.length,
    ruleCount: rules.length,
    transforms,
    ruleTypes,
    profile: template.profile,
    tags: template.tags,
  }
}

export const summariseConsolidation = (payload) => {
  const mappings = normaliseMappings(payload)
  const rules = normaliseRules(payload)
  const targets = mappings.map(mapping => mapping.target.toLowerCase()).filter(Boolean)
  const idColumns = targets.filter(target => target.includes('id'))
  const contactColumns = targets.filter(target => target.includes('contact'))
  const ruleTypes = Array.from(new Set(rules.map(rule => rule.type).filter(Boolean)))
  return {
    mappingCount: mappings.length,
    ruleCount: rules.length,
    idColumns,
    contactColumns,
    ruleTypes,
  }
}

export const buildContractOutput = ({ template, outputDir, format = 'yaml' }) => {
  const profile = typeof template.profile === 'string' ? template.profile : 'generic'
  const safeName = slugify(template.name ?? template.id ?? profile)
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  const filename = `${safeName}-${timestamp}.${format}`
  return {
    profile,
    filename,
    outputPath: path.join(outputDir, filename),
  }
}

export const aggregateConsolidationTelemetry = (templates = []) => {
  let totalMappings = 0
  let totalRules = 0
  const profileCounts = new Map()
  const ruleTypes = new Map()

  templates.forEach(template => {
    const summary = summariseTemplate(template, template.payload)
    totalMappings += summary.mappingCount
    totalRules += summary.ruleCount
    if (summary.profile) {
      profileCounts.set(summary.profile, (profileCounts.get(summary.profile) ?? 0) + 1)
    }
    summary.ruleTypes.forEach(type => {
      ruleTypes.set(type, (ruleTypes.get(type) ?? 0) + 1)
    })
  })

  const profileBreakdown = Array.from(profileCounts.entries())
    .map(([profile, count]) => ({ profile, count }))
    .sort((a, b) => b.count - a.count)

  const popularRuleTypes = Array.from(ruleTypes.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)

  return {
    totalTemplates: templates.length,
    totalMappings,
    totalRules,
    profileBreakdown,
    popularRuleTypes,
  }
}

export const slugifyTemplate = slugify
