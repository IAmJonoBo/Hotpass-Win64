import { useMemo, useState } from 'react'
import { Loader2, Map, SlidersHorizontal, CheckCircle2, BookOpen, CloudUpload, PencilRuler, ListChecks } from 'lucide-react'
import { useStoredImportProfiles } from '@/api/imports'
import type { ImportTemplate, ImportTemplatePayload } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TemplatePicker } from '@/components/import/TemplatePicker'
import { TemplateManagerDrawer } from '@/components/import/TemplateManagerDrawer'
import { cn } from '@/lib/utils'

const wizardSteps = [
  { id: 'upload', title: 'Upload', description: 'Queue files and review profiling summary', icon: CloudUpload },
  { id: 'profile', title: 'Profile', description: 'Confirm inferred roles, join keys, and issues', icon: BookOpen },
  { id: 'mapping', title: 'Mapping', description: 'Adjust column mappings and rename rules', icon: Map },
  { id: 'rules', title: 'Rules', description: 'Toggle remediation rules and enrichment options', icon: SlidersHorizontal },
  { id: 'summary', title: 'Summary', description: 'Review validation checklist before running', icon: CheckCircle2 },
] as const

export function ImportsWizard() {
  const [activeStep, setActiveStep] = useState(0)
  const [selectedTemplate, setSelectedTemplate] = useState<ImportTemplate | null>(null)
  const [isTemplateManagerOpen, setTemplateManagerOpen] = useState(false)
  const { data: storedProfiles = [], isLoading: profilesLoading } = useStoredImportProfiles()

  const activeStepDetails = wizardSteps[activeStep]
  const selectedTemplatePayload = useMemo<ImportTemplatePayload | null>(
    () => (selectedTemplate ? selectedTemplate.payload ?? null : null),
    [selectedTemplate],
  )

  const renderStepContent = () => {
    const stepId = activeStepDetails.id
    switch (stepId) {
      case 'mapping':
        return (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Preview of column mappings coming soon. Your selected template will seed the default rename/normalisation rules.
            </p>
            {selectedTemplatePayload?.import_mappings && Array.isArray(selectedTemplatePayload.import_mappings) && selectedTemplatePayload.import_mappings.length > 0 ? (
              <div className="space-y-2 rounded-2xl border border-border/60 bg-background/80 px-3 py-3 text-xs">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <PencilRuler className="h-4 w-4" />
                  Sample mappings
                </div>
                <ul className="space-y-1">
                  {selectedTemplatePayload.import_mappings.slice(0, 4).map((mapping, index) => (
                    <li key={index} className="flex items-center justify-between gap-2 rounded-xl border border-border/50 bg-card/70 px-2 py-1">
                      <span className="truncate font-medium" title={String(mapping.source ?? '')}>
                        {String(mapping.source ?? '') || '(source)'}
                      </span>
                      <span className="text-muted-foreground">→</span>
                      <span className="truncate text-muted-foreground" title={String(mapping.target ?? '')}>
                        {String(mapping.target ?? '') || '(target)'}
                      </span>
                    </li>
                  ))}
                </ul>
                {selectedTemplatePayload.import_mappings.length > 4 && (
                  <p className="text-[11px] text-muted-foreground">
                    +{selectedTemplatePayload.import_mappings.length - 4} additional mappings
                  </p>
                )}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3 text-xs text-muted-foreground">
                No mappings defined yet. Once implemented, you&rsquo;ll be able to rename columns and define defaults here.
              </div>
            )}
          </div>
        )
      case 'rules':
        return (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Rule toggles will surface here to control normalisation, dedupe, geocoding, and compliance safeguards per profile.
            </p>
            {selectedTemplatePayload?.import_rules && Array.isArray(selectedTemplatePayload.import_rules) && selectedTemplatePayload.import_rules.length > 0 ? (
              <div className="space-y-2 rounded-2xl border border-border/60 bg-background/80 px-3 py-3 text-xs">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <ListChecks className="h-4 w-4" />
                  Active rules
                </div>
                <ul className="space-y-1">
                  {selectedTemplatePayload.import_rules.slice(0, 5).map((rule, index) => (
                    <li key={index} className="rounded-xl border border-border/50 bg-card/70 px-2 py-1">
                      <span className="font-medium text-foreground">{String(rule.type ?? 'rule')}</span>
                      {Array.isArray(rule.columns) && rule.columns.length > 0 && (
                        <span className="ml-2 text-muted-foreground">
                          ({rule.columns.slice(0, 3).join(', ')}
                          {rule.columns.length > 3 ? `, +${rule.columns.length - 3}` : ''})
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3 text-xs text-muted-foreground">
                Add rules such as `normalize_date`, `fill_missing`, or compliance checks to see them listed here.
              </div>
            )}
          </div>
        )
      default:
        return (
          <p className="text-xs text-muted-foreground">
            Placeholder surface for {activeStepDetails.title.toLowerCase()} controls. Upcoming iterations will embed upload widgets,
            mapping editors, rule toggles, and validation summaries here.
          </p>
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
          <span>Future releases will add template editing, diff previews, and run scheduling.</span>
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
              <div className="mt-1 space-y-2">
                {renderStepContent()}
                {selectedTemplate ? (
                  <p className="text-[11px] text-muted-foreground">
                    Selected template <span className="font-semibold text-foreground">{selectedTemplate.name}</span> will prefill defaults during run execution.
                  </p>
                ) : (
                  <p className="text-[11px] text-muted-foreground">
                    Select a template to prepopulate mapping/rule steps or continue with the generic profile defaults.
                  </p>
                )}
              </div>
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
            onSelect={(template) => setSelectedTemplate(template)}
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
                  Showing 5 of {storedProfiles.length}. Templates with attached profiles will provide richer diffs in later iterations.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <TemplateManagerDrawer
        open={isTemplateManagerOpen}
        onOpenChange={setTemplateManagerOpen}
        onSelect={(template) => {
          setSelectedTemplate(template)
          setTemplateManagerOpen(false)
        }}
      />
    </div>
  )
}
