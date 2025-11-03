import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Loader2,
  Map,
  SlidersHorizontal,
  CheckCircle2,
  BookOpen,
  CloudUpload,
  PencilRuler,
  ListChecks,
  Plus,
  Trash2,
  Copy,
  ArrowRight,
  Download,
  ShieldAlert,
} from 'lucide-react'
import { useStoredImportProfiles, usePublishTemplateContract } from '@/api/imports'
import type { ImportTemplate, ImportTemplatePayload } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { TemplatePicker } from '@/components/import/TemplatePicker'
import { TemplateManagerDrawer } from '@/components/import/TemplateManagerDrawer'
import { ConsolidationPreview } from '@/components/import/ConsolidationPreview'
import { cn } from '@/lib/utils'
import { buildTemplateContract, buildTemplateDiff, summariseTemplate } from '@/lib/importTemplates'

const wizardSteps = [
  { id: 'upload', title: 'Upload', description: 'Queue files and review profiling summary', icon: CloudUpload },
  { id: 'profile', title: 'Profile', description: 'Confirm inferred roles, join keys, and issues', icon: BookOpen },
  { id: 'mapping', title: 'Mapping', description: 'Adjust column mappings and rename rules', icon: Map },
  { id: 'rules', title: 'Rules', description: 'Toggle remediation rules and enrichment options', icon: SlidersHorizontal },
  { id: 'summary', title: 'Summary', description: 'Review validation checklist before running', icon: CheckCircle2 },
] as const

type MappingRow = {
  id: string
  source: string
  target: string
  defaultValue: string
  transform: string
  strip: boolean
  drop: boolean
}

type RuleRow = {
  id: string
  type: string
  columns: string
  config: string
}

const transformOptions = ['', 'lower', 'upper', 'title', 'strip', 'trim']

const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/_{2,}/g, '_')
    .replace(/^_|_$/g, '')

const createId = () =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `tmp-${Date.now()}-${Math.random().toString(16).slice(2)}`

const parseMappings = (payload: ImportTemplatePayload | null | undefined): MappingRow[] => {
  if (!payload?.import_mappings || !Array.isArray(payload.import_mappings)) return []
  return payload.import_mappings.map((mapping) => ({
    id: createId(),
    source: typeof mapping.source === 'string' ? mapping.source : '',
    target: typeof mapping.target === 'string' ? mapping.target : '',
    defaultValue: typeof mapping.default === 'string' ? mapping.default : '',
    transform: typeof mapping.transform === 'string' ? mapping.transform : '',
    strip: Boolean(mapping.strip),
    drop: Boolean(mapping.drop),
  }))
}

const parseRules = (payload: ImportTemplatePayload | null | undefined): RuleRow[] => {
  if (!payload?.import_rules || !Array.isArray(payload.import_rules)) return []
  return payload.import_rules.map((rule) => {
    const { type, columns, ...rest } = rule as Record<string, unknown>
    const columnsText = Array.isArray(columns)
      ? columns.map(value => String(value)).join(', ')
      : typeof columns === 'string'
        ? columns
        : ''
    const config = Object.keys(rest).length > 0 ? JSON.stringify(rest, null, 2) : ''
    return {
      id: createId(),
      type: typeof type === 'string' ? type : '',
      columns: columnsText,
      config,
    }
  })
}

const TextArea = (props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea
    {...props}
    className={cn(
      'w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
      props.className,
    )}
  />
)

export function ImportsWizard() {
  const [activeStep, setActiveStep] = useState(0)
  const [selectedTemplate, setSelectedTemplate] = useState<ImportTemplate | null>(null)
  const [isTemplateManagerOpen, setTemplateManagerOpen] = useState(false)
  const [mappingRows, setMappingRows] = useState<MappingRow[]>([])
  const [ruleRows, setRuleRows] = useState<RuleRow[]>([])
  const [ruleErrors, setRuleErrors] = useState<Record<string, string | null>>({})
  const [exportMessage, setExportMessage] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [contractMessage, setContractMessage] = useState<string | null>(null)
  const [contractError, setContractError] = useState<string | null>(null)
  const publishContractMutation = usePublishTemplateContract()

  const { data: storedProfiles = [], isLoading: profilesLoading } = useStoredImportProfiles()

  const activeStepDetails = wizardSteps[activeStep]
  const selectedTemplatePayload = useMemo<ImportTemplatePayload | null>(
    () => (selectedTemplate ? selectedTemplate.payload ?? null : null),
    [selectedTemplate],
  )
  const latestProfile = storedProfiles[0]?.profile ?? null

  useEffect(() => {
    setMappingRows(parseMappings(selectedTemplatePayload))
    setRuleRows(parseRules(selectedTemplatePayload))
    setRuleErrors({})
    setExportMessage(null)
    setExportError(null)
    setContractMessage(null)
    setContractError(null)
  }, [selectedTemplatePayload])

  const updateMappingRow = useCallback((id: string, patch: Partial<MappingRow>) => {
    setMappingRows(rows => rows.map(row => (row.id === id ? { ...row, ...patch } : row)))
  }, [])

  const removeMappingRow = useCallback((id: string) => {
    setMappingRows(rows => rows.filter(row => row.id !== id))
  }, [])

  const duplicateMappingRow = useCallback((row: MappingRow) => {
    setMappingRows(rows => [...rows, { ...row, id: createId() }])
  }, [])

  const addMappingRow = useCallback(() => {
    setMappingRows(rows => [
      ...rows,
      {
        id: createId(),
        source: '',
        target: '',
        defaultValue: '',
        transform: '',
        strip: false,
        drop: false,
      },
    ])
  }, [])

  const seedMappingsFromProfile = useCallback(() => {
    if (!latestProfile) return
    const firstSheet = latestProfile.sheets[0]
    if (!firstSheet) return
    const existingSources = new Set(mappingRows.map(row => row.source.toLowerCase()))
    const newRows: MappingRow[] = []
    firstSheet.columns.forEach(column => {
      const sourceName = column.name ?? ''
      if (!sourceName || existingSources.has(sourceName.toLowerCase())) return
      newRows.push({
        id: createId(),
        source: sourceName,
        target: slugify(sourceName),
        defaultValue: '',
        transform: column.inferred_type === 'string' ? 'trim' : '',
        strip: true,
        drop: false,
      })
      existingSources.add(sourceName.toLowerCase())
    })
    if (newRows.length > 0) {
      setMappingRows(rows => [...rows, ...newRows])
    }
  }, [latestProfile, mappingRows])

  const updateRuleRow = useCallback((id: string, patch: Partial<RuleRow>) => {
    setRuleRows(rows => rows.map(row => (row.id === id ? { ...row, ...patch } : row)))
  }, [])

  const removeRuleRow = useCallback((id: string) => {
    setRuleRows(rows => rows.filter(row => row.id !== id))
    setRuleErrors(errors => {
      const next = { ...errors }
      delete next[id]
      return next
    })
  }, [])

  const addRuleRow = useCallback(() => {
    setRuleRows(rows => [
      ...rows,
      {
        id: createId(),
        type: '',
        columns: '',
        config: '',
      },
    ])
  }, [])

  const handleRuleConfigChange = useCallback((id: string, value: string) => {
    updateRuleRow(id, { config: value })
    if (!value.trim()) {
      setRuleErrors(errors => ({ ...errors, [id]: null }))
      return
    }
    try {
      JSON.parse(value)
      setRuleErrors(errors => ({ ...errors, [id]: null }))
    } catch (error) {
      setRuleErrors(errors => ({
        ...errors,
        [id]: error instanceof Error ? error.message : 'Invalid JSON',
      }))
    }
  }, [updateRuleRow])

  const hasRuleErrors = useMemo(() => Object.values(ruleErrors).some(Boolean), [ruleErrors])

  const createPayloadFromRows = useCallback((): ImportTemplatePayload => {
    const mappings = mappingRows
      .filter(row => row.source || row.target)
      .map(row => {
        const spec: Record<string, unknown> = {}
        if (row.source) spec.source = row.source
        if (row.target) spec.target = row.target
        if (row.defaultValue) spec.default = row.defaultValue
        if (row.transform) spec.transform = row.transform
        if (row.strip) spec.strip = true
        if (row.drop) spec.drop = true
        return spec
      })
    const rules: Record<string, unknown>[] = []
    ruleRows.forEach(row => {
      if (!row.type) return
      const spec: Record<string, unknown> = { type: row.type }
      const columns = row.columns
        .split(',')
        .map(column => column.trim())
        .filter(Boolean)
      if (columns.length) spec.columns = columns
      if (row.config.trim()) {
        spec.config = JSON.parse(row.config)
      }
      rules.push(spec)
    })
    return {
      import_mappings: mappings,
      import_rules: rules,
    }
  }, [mappingRows, ruleRows])

  const draftPayload = useMemo<ImportTemplatePayload | null>(() => {
    if (hasRuleErrors) return null
    try {
      return createPayloadFromRows()
    } catch {
      return null
    }
  }, [createPayloadFromRows, hasRuleErrors])

  const templateDiff = useMemo(
    () => (selectedTemplatePayload && draftPayload ? buildTemplateDiff(selectedTemplatePayload, draftPayload) : null),
    [selectedTemplatePayload, draftPayload],
  )

  const selectedTemplateSummary = useMemo(
    () => summariseTemplate(selectedTemplate ?? null, selectedTemplatePayload ?? null),
    [selectedTemplate, selectedTemplatePayload],
  )

  const validationIssues = useMemo(() => {
    const issues: string[] = []
    const seenSources = new Map<string, number>()
    mappingRows.forEach(row => {
      const key = row.source.trim().toLowerCase()
      if (!key) return
      seenSources.set(key, (seenSources.get(key) ?? 0) + 1)
    })
    if (Array.from(seenSources.values()).some(count => count > 1)) {
      issues.push('Duplicate source columns detected across mappings.')
    }
    if (!mappingRows.some(row => row.source && row.target)) {
      issues.push('Add at least one mapping with both source and target columns.')
    }
    if (ruleRows.some(row => !row.type && (row.columns || row.config))) {
      issues.push('One or more rule rows are missing a type.')
    }
    if (hasRuleErrors) {
      issues.push('Resolve rule configuration JSON errors.')
    }
    return issues
  }, [mappingRows, ruleRows, hasRuleErrors])

  const handleExportTemplate = useCallback(() => {
    if (!draftPayload || validationIssues.length > 0) {
      setExportMessage(null)
      setExportError('Resolve validation issues before exporting the template.')
      return
    }
    const metadata = {
      name: selectedTemplate?.name ?? 'wizard-template',
      description: selectedTemplate?.description ?? '',
      profile: selectedTemplate?.profile ?? 'generic',
      tags: selectedTemplate?.tags ?? [],
      payload: draftPayload,
      exportedAt: new Date().toISOString(),
    }
    const blob = new Blob([`${JSON.stringify(metadata, null, 2)}\n`], { type: 'application/json' })
    const filename = `${slugify(metadata.name)}-template.json`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    setExportMessage(`Template exported as ${filename}`)
    setExportError(null)
  }, [draftPayload, selectedTemplate, validationIssues])

  const handleExportContract = useCallback(() => {
    if (!draftPayload || validationIssues.length > 0) {
      setContractMessage(null)
      setContractError('Resolve validation issues before exporting the contract.')
      return
    }
    const contract = buildTemplateContract({
      template: {
        name: selectedTemplate?.name ?? 'wizard-template',
        profile: selectedTemplate?.profile,
        description: selectedTemplate?.description,
        tags: selectedTemplate?.tags,
      },
      payload: draftPayload,
      origin: 'wizard-ui',
    })
    const filename = `${slugify(contract.template.name)}-contract.json`
    const blob = new Blob([`${JSON.stringify(contract, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    setContractMessage(`Contract exported as ${filename}`)
    setContractError(null)
  }, [draftPayload, selectedTemplate, validationIssues])

  const handlePublishContract = useCallback(() => {
    if (!selectedTemplate) {
      setContractMessage(null)
      setContractError('Select a template before publishing the contract.')
      return
    }
    if (validationIssues.length > 0 || hasRuleErrors) {
      setContractMessage(null)
      setContractError('Resolve validation issues before publishing the contract.')
      return
    }
    publishContractMutation.mutate(
      { templateId: selectedTemplate.id, format: 'yaml' },
      {
        onSuccess: ({ job }) => {
          setContractMessage(`Contract job ${job.id} queued.`)
          setContractError(null)
        },
        onError: (error) => {
          setContractMessage(null)
          setContractError(error instanceof Error ? error.message : 'Failed to publish contract')
        },
      },
    )
  }, [selectedTemplate, validationIssues, hasRuleErrors, publishContractMutation])

  const handleDownloadPreview = useCallback(() => {
    const summary = {
      profile: selectedTemplate?.profile ?? 'generic',
      mappings: mappingRows.length,
      rules: ruleRows.length,
      generatedAt: new Date().toISOString(),
      notes: 'Consolidation preview summarises expected outputs; detailed diff tooling coming soon.',
    }
    const blob = new Blob([`${JSON.stringify(summary, null, 2)}\n`], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `consolidation-preview-${summary.profile}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [mappingRows.length, ruleRows.length, selectedTemplate])

  const setTemplateAndClose = useCallback((template: ImportTemplate | null) => {
    setSelectedTemplate(template)
    setTemplateManagerOpen(false)
  }, [])

  const renderProfileStep = () => (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Profiling summaries help validate sheet roles and join keys before mappings are configured.
      </p>
      {storedProfiles.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3 text-xs text-muted-foreground">
          Attach profiling payloads from the Dataset Import panel to see them listed here.
        </div>
      ) : (
        <ul className="space-y-2">
          {storedProfiles.slice(0, 3).map(profile => (
            <li key={profile.id} className="rounded-2xl border border-border/60 bg-card/80 px-3 py-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-foreground truncate">{profile.profile.workbook}</p>
                  <p className="text-muted-foreground">
                    {profile.profile.sheets.length} sheets · saved {new Date(profile.createdAt).toLocaleString()}
                  </p>
                </div>
                {profile.tags?.length ? (
                  <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                    {profile.tags[0]}
                  </Badge>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      {latestProfile && (
        <p className="text-[11px] text-muted-foreground">
          Latest profile workbook: <span className="font-semibold text-foreground">{latestProfile.workbook}</span>
        </p>
      )}
    </div>
  )

  const renderMappingStep = () => (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Define inbound → normalized column mappings. Use template defaults or seed from profiling.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={seedMappingsFromProfile} disabled={!latestProfile}>
            <Copy className="mr-2 h-3 w-3" />
            Use profile columns
          </Button>
          <Button variant="ghost" size="sm" onClick={addMappingRow}>
            <Plus className="mr-1 h-3 w-3" />
            Add mapping
          </Button>
        </div>
      </div>

      {mappingRows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3 text-xs text-muted-foreground">
          No mappings yet. Add rows manually or seed from the latest profiling payload.
        </div>
      ) : (
        <div className="space-y-3">
          {mappingRows.map((row, index) => (
            <div key={row.id} className="space-y-3 rounded-2xl border border-border/60 bg-background/80 px-3 py-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Mapping #{index + 1}</span>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={() => duplicateMappingRow(row)}>
                    <Copy className="mr-1 h-3 w-3" />
                    Duplicate
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => removeMappingRow(row.id)}>
                    <Trash2 className="mr-1 h-3 w-3" />
                    Remove
                  </Button>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Source column</label>
                  <Input
                    value={row.source}
                    onChange={(event) => updateMappingRow(row.id, { source: event.target.value })}
                    placeholder="Organisation Name"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Target column</label>
                  <Input
                    value={row.target}
                    onChange={(event) => updateMappingRow(row.id, { target: event.target.value })}
                    placeholder="organization_name"
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-[1fr_1fr_0.7fr]">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Default value</label>
                  <Input
                    value={row.defaultValue}
                    onChange={(event) => updateMappingRow(row.id, { defaultValue: event.target.value })}
                    placeholder="Optional default"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Transform</label>
                  <select
                    value={row.transform}
                    onChange={(event) => updateMappingRow(row.id, { transform: event.target.value })}
                    className="h-9 w-full rounded-xl border border-border/70 bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {transformOptions.map(option => (
                      <option key={option} value={option}>
                        {option || 'None'}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-4 rounded-xl border border-border/60 bg-card/70 px-3 py-2 text-xs">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border border-border/60"
                      checked={row.strip}
                      onChange={(event) => updateMappingRow(row.id, { strip: event.target.checked })}
                    />
                    Strip
                  </label>
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border border-border/60"
                      checked={row.drop}
                      onChange={(event) => updateMappingRow(row.id, { drop: event.target.checked })}
                    />
                    Drop
                  </label>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  const renderRulesStep = () => (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Configure rule pipeline for normalization, dedupe, geocoding, or compliance. Rules accept additional JSON config.
        </p>
        <Button variant="ghost" size="sm" onClick={addRuleRow}>
          <Plus className="mr-1 h-3 w-3" />
          Add rule
        </Button>
      </div>
      {ruleRows.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3 text-xs text-muted-foreground">
          No rules configured yet. Add rules to enforce normalization or validation before running the pipeline.
        </div>
      ) : (
        <div className="space-y-3">
          {ruleRows.map((row, index) => (
            <div key={row.id} className="space-y-3 rounded-2xl border border-border/60 bg-background/80 px-3 py-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Rule #{index + 1}</span>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={() => removeRuleRow(row.id)}>
                    <Trash2 className="mr-1 h-3 w-3" />
                    Remove
                  </Button>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Rule type</label>
                  <Input
                    value={row.type}
                    onChange={(event) => updateRuleRow(row.id, { type: event.target.value })}
                    placeholder="normalize_date / dedupe / fill_missing"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold uppercase text-muted-foreground">Columns</label>
                  <Input
                    value={row.columns}
                    onChange={(event) => updateRuleRow(row.id, { columns: event.target.value })}
                    placeholder="email, phone"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-semibold uppercase text-muted-foreground">Config (JSON)</label>
                <TextArea
                  rows={8}
                  value={row.config}
                  onChange={(event) => handleRuleConfigChange(row.id, event.target.value)}
                  placeholder={'{\n  "output_format": "%Y-%m-%d"\n}'}
                />
                {ruleErrors[row.id] && (
                  <p className="text-[11px] text-red-600 dark:text-red-400">{ruleErrors[row.id]}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  const renderSummaryStep = () => {
    const hasIssues = validationIssues.length > 0
    return (
      <div className="space-y-3">
        <div
          className={cn(
            'rounded-2xl border px-3 py-3 text-xs',
            hasIssues
              ? 'border-yellow-500/50 bg-yellow-500/10 text-yellow-800 dark:text-yellow-300'
              : 'border-green-500/50 bg-green-500/10 text-green-700 dark:text-green-300',
          )}
        >
          <div className="flex items-center gap-2">
            {hasIssues ? (
              <ShieldAlert className="h-4 w-4" />
            ) : (
              <CheckCircle2 className="h-4 w-4" />
            )}
            <span className="font-semibold text-foreground">
              {hasIssues ? 'Validation checks need attention' : 'All validation checks passed'}
            </span>
          </div>
          {hasIssues ? (
            <ul className="mt-2 space-y-1 text-muted-foreground">
              {validationIssues.map((issue, index) => (
                <li key={index} className="flex items-center gap-2">
                  <ShieldAlert className="h-3 w-3 text-yellow-600 dark:text-yellow-300" />
                  <span>{issue}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-muted-foreground">
              No blocking issues detected. You can proceed to run the pipeline or export the configuration.
            </p>
          )}
        </div>
        <ul className="space-y-2 text-xs">
          <li className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/80 px-3 py-2">
            <ArrowRight className="h-3 w-3 text-primary" />
            {mappingRows.length} mapping rule(s) ready.
          </li>
          <li className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/80 px-3 py-2">
            <ArrowRight className="h-3 w-3 text-primary" />
            {ruleRows.length} preprocessing rule(s) configured.
          </li>
          <li className="flex items-center gap-2 rounded-xl border border-border/60 bg-card/80 px-3 py-2">
            <ArrowRight className="h-3 w-3 text-primary" />
            Template: {selectedTemplate?.name ?? 'Not selected'} ({selectedTemplate?.profile ?? 'generic'} profile)
          </li>
        </ul>
      </div>
    )
  }

  const renderStepContent = () => {
    const stepId = activeStepDetails.id
    switch (stepId) {
      case 'profile':
        return renderProfileStep()
      case 'mapping':
        return renderMappingStep()
      case 'rules':
        return renderRulesStep()
      case 'summary':
        return renderSummaryStep()
      default:
        return (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Use the Smart Import wizard to capture the context required before executing the refinement pipeline.
            </p>
            <p className="text-[11px] text-muted-foreground">
              As steps are completed the summary will indicate readiness. Upload UI integration lands in a subsequent sprint.
            </p>
          </div>
        )
    }
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Smart Import Wizard</h1>
          <p className="text-sm text-muted-foreground">
            Guided ingest workflow that combines profiling insights, template defaults, and human-in-the-loop checks.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="uppercase">Preview</Badge>
          <span>Template editing, diff previews, and scheduling will follow the Stage 4 milestone.</span>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Wizard steps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="space-y-3">
              {wizardSteps.map((step, index) => {
                const Icon = step.icon
                const isActive = index === activeStep
                const isComplete = index < activeStep
                return (
                  <li key={step.id}>
                    <button
                      type="button"
                      onClick={() => setActiveStep(index)}
                      className={cn(
                        'w-full rounded-2xl border border-border/60 bg-card/80 px-4 py-3 text-left transition',
                        isActive ? 'ring-2 ring-primary/60' : 'hover:bg-muted/60',
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={cn('h-5 w-5', isComplete ? 'text-green-500' : 'text-primary')} />
                        <div>
                          <p className="text-sm font-semibold text-foreground">{step.title}</p>
                          <p className="text-xs text-muted-foreground">{step.description}</p>
                        </div>
                        {isComplete && (
                          <Badge variant="outline" className="ml-auto text-[10px] uppercase tracking-wide text-green-600">
                            Complete
                          </Badge>
                        )}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ol>

            <div className="rounded-2xl border border-dashed border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground">
              <p className="font-semibold text-foreground">{activeStepDetails.title}</p>
              <div className="mt-1 space-y-2">{renderStepContent()}</div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" disabled={activeStep === 0} onClick={() => setActiveStep(Math.max(0, activeStep - 1))}>
                Back
              </Button>
              <Button
                size="sm"
                onClick={() => setActiveStep(Math.min(wizardSteps.length - 1, activeStep + 1))}
                disabled={activeStep === wizardSteps.length - 1}
              >
                Next
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <TemplatePicker
            selectedTemplateId={selectedTemplate?.id ?? null}
            onSelect={(template) => setTemplateAndClose(template)}
            onManage={() => setTemplateManagerOpen(true)}
          />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent profiling payloads</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {profilesLoading ? (
                <div className="flex items-center gap-2 rounded-2xl border border-border/60 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading stored profiles…
                </div>
              ) : storedProfiles.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/60 bg-muted/20 px-3 py-4 text-xs text-muted-foreground">
                  Profiles attached during imports will appear here for quick reuse.
                </div>
              ) : (
                <ul className="space-y-2">
                  {storedProfiles.slice(0, 5).map(profile => (
                    <li key={profile.id} className="rounded-2xl border border-border/60 bg-card/80 px-3 py-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="font-semibold text-foreground truncate">{profile.profile.workbook}</p>
                          <p className="text-muted-foreground">
                            {profile.profile.sheets.length} sheets · saved {new Date(profile.createdAt).toLocaleString()}
                          </p>
                        </div>
                        {profile.tags?.length ? (
                          <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                            {profile.tags[0]}
                          </Badge>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              {storedProfiles.length > 5 && (
                <p className="text-[11px] text-muted-foreground">
                  Showing 5 of {storedProfiles.length}. Template defaults will include profiling metadata in a later release.
                </p>
              )}
            </CardContent>
          </Card>

          <ConsolidationPreview
            profileName={selectedTemplate?.profile ?? latestProfile?.sheets?.[0]?.role ?? 'generic'}
            mappingCount={mappingRows.length}
            ruleCount={ruleRows.length}
            onDownload={handleDownloadPreview}
          />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Template actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Export the current wizard configuration as JSON for CLI reuse or versioning, compare against the stored template, or download a contract snapshot.
              </p>
              {selectedTemplate && selectedTemplateSummary ? (
                <div className="space-y-1 rounded-2xl border border-border/60 bg-card/70 px-3 py-2 text-xs">
                  <p className="font-semibold text-foreground">Selected template summary</p>
                  <p>{selectedTemplateSummary.mappingCount} mapping(s) · {selectedTemplateSummary.ruleCount} rule(s)</p>
                  {selectedTemplateSummary.transforms.length > 0 && (
                    <p className="text-muted-foreground">Transforms: {selectedTemplateSummary.transforms.join(', ')}</p>
                  )}
                  {selectedTemplateSummary.ruleTypes.length > 0 && (
                    <p className="text-muted-foreground">Rule types: {selectedTemplateSummary.ruleTypes.join(', ')}</p>
                  )}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-2 text-xs text-muted-foreground">
                  Select or create a template to enable diff and contract tooling.
                </div>
              )}
              {selectedTemplate && templateDiff && (
                <div className="space-y-1 rounded-2xl border border-border/60 bg-background/80 px-3 py-2 text-xs">
                  <p className="font-semibold text-foreground">Diff vs stored template</p>
                  <p>
                    Mappings: +{templateDiff.addedMappings.length} / -{templateDiff.removedMappings.length} / Δ{templateDiff.changedMappings.length}
                  </p>
                  <p>
                    Rules: +{templateDiff.addedRules.length} / -{templateDiff.removedRules.length} / Δ{templateDiff.changedRules.length}
                  </p>
                </div>
              )}
              {hasRuleErrors && (
                <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-700 dark:text-yellow-400">
                  Resolve rule configuration JSON errors before exporting.
                </div>
              )}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                <Button size="sm" onClick={handleExportTemplate} disabled={!draftPayload || validationIssues.length > 0}>
                  <Download className="mr-2 h-4 w-4" />
                  Export template JSON
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleExportContract}
                  disabled={!draftPayload || validationIssues.length > 0}
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download contract JSON
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handlePublishContract}
                  disabled={
                    !selectedTemplate ||
                    validationIssues.length > 0 ||
                    hasRuleErrors ||
                    publishContractMutation.isPending
                  }
                >
                  {publishContractMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Publishing…
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      Publish contract (CLI)
                    </>
                  )}
                </Button>
              </div>
              {exportMessage && (
                <div className="rounded-xl border border-green-500/40 bg-green-500/10 px-3 py-2 text-xs text-green-600 dark:text-green-400">
                  {exportMessage}
                </div>
              )}
              {exportError && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                  {exportError}
                </div>
              )}
              {contractMessage && (
                <div className="rounded-xl border border-green-500/40 bg-green-500/10 px-3 py-2 text-xs text-green-600 dark:text-green-400">
                  {contractMessage}
                </div>
              )}
              {contractError && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                  {contractError}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <TemplateManagerDrawer
        open={isTemplateManagerOpen}
        onOpenChange={setTemplateManagerOpen}
        onSelect={(template) => template && setTemplateAndClose(template)}
      />
    </div>
  )
}
