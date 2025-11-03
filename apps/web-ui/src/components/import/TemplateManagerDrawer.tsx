import { useState, useMemo, TextareaHTMLAttributes } from 'react'
import { Sheet, SheetBody, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { useImportTemplates, useImportTemplateUpsert, useImportTemplateDelete } from '@/api/imports'
import type { ImportTemplate, ImportTemplatePayload } from '@/types'
import { cn } from '@/lib/utils'

interface TemplateManagerDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect?: (template: ImportTemplate) => void
}

interface TemplateFormState {
  id: string | null
  name: string
  description: string
  profile: string
  tags: string
  payload: string
}

const defaultForm: TemplateFormState = {
  id: null,
  name: '',
  description: '',
  profile: '',
  tags: '',
  payload: '{\n  "import_mappings": [],\n  "import_rules": []\n}',
}

function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(
        'w-full rounded-xl border border-border/70 bg-background px-3 py-2 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
        props.className,
      )}
    />
  )
}

export function TemplateManagerDrawer({ open, onOpenChange, onSelect }: TemplateManagerDrawerProps) {
  const { data: templates = [], isLoading, isError, error } = useImportTemplates()
  const upsertTemplate = useImportTemplateUpsert()
  const deleteTemplate = useImportTemplateDelete()

  const [form, setForm] = useState<TemplateFormState>(defaultForm)
  const [formError, setFormError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const editingTemplate = useMemo(
    () => (form.id ? templates.find(template => template.id === form.id) ?? null : null),
    [form.id, templates],
  )

  const resetForm = () => {
    setForm(defaultForm)
    setFormError(null)
  }

  const handleEdit = (template: ImportTemplate) => {
    setForm({
      id: template.id,
      name: template.name,
      description: template.description ?? '',
      profile: template.profile ?? '',
      tags: template.tags?.join(', ') ?? '',
      payload: JSON.stringify(template.payload ?? {}, null, 2),
    })
    setFormError(null)
    setSuccessMessage(null)
  }

  const handleDelete = async (template: ImportTemplate) => {
    if (!window.confirm(`Delete template "${template.name}"? This cannot be undone.`)) {
      return
    }
    try {
      await deleteTemplate.mutateAsync(template.id)
      if (form.id === template.id) {
        resetForm()
      }
      setSuccessMessage(`Template "${template.name}" deleted.`)
    } catch (deleteError) {
      setFormError(deleteError instanceof Error ? deleteError.message : 'Failed to delete template')
    }
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    setSuccessMessage(null)

    if (!form.name.trim()) {
      setFormError('Template name is required.')
      return
    }

    let parsedPayload: ImportTemplatePayload
    try {
      parsedPayload = JSON.parse(form.payload) as ImportTemplatePayload
    } catch (payloadError) {
      setFormError(payloadError instanceof Error ? payloadError.message : 'Payload must be valid JSON')
      return
    }

    const tags = form.tags
      .split(',')
      .map(tag => tag.trim())
      .filter(Boolean)

    try {
      const result = await upsertTemplate.mutateAsync({
        id: form.id ?? undefined,
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        profile: form.profile.trim() || undefined,
        tags,
        payload: parsedPayload,
      })
      setSuccessMessage(`Template "${result.name}" saved.`)
      if (!form.id) {
        setForm({
          id: result.id,
          name: result.name,
          description: result.description ?? '',
          profile: result.profile ?? '',
          tags: result.tags?.join(', ') ?? '',
          payload: JSON.stringify(result.payload ?? {}, null, 2),
        })
      }
      if (onSelect) {
        onSelect(result)
      }
    } catch (mutationError) {
      setFormError(mutationError instanceof Error ? mutationError.message : 'Failed to save template')
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader onClose={() => onOpenChange(false)}>
          <SheetTitle>{form.id ? 'Edit template' : 'Create template'}</SheetTitle>
        </SheetHeader>
        <SheetBody className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <section className="space-y-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Name</label>
                <Input
                  required
                  value={form.name}
                  onChange={(event) => setForm(prev => ({ ...prev, name: event.target.value }))}
                  placeholder="Customer onboarding template"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Description</label>
                <Input
                  value={form.description}
                  onChange={(event) => setForm(prev => ({ ...prev, description: event.target.value }))}
                  placeholder="Optional short description"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase text-muted-foreground">Profile</label>
                  <Input
                    value={form.profile}
                    onChange={(event) => setForm(prev => ({ ...prev, profile: event.target.value }))}
                    placeholder="generic / aviation / compliance"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-semibold uppercase text-muted-foreground">Tags</label>
                  <Input
                    value={form.tags}
                    onChange={(event) => setForm(prev => ({ ...prev, tags: event.target.value }))}
                    placeholder="aviation, pilot, qa-ready"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase text-muted-foreground">Payload (JSON)</label>
                <TextArea
                  rows={16}
                  spellCheck={false}
                  value={form.payload}
                  onChange={(event) => setForm(prev => ({ ...prev, payload: event.target.value }))}
                />
              </div>
              {formError && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                  {formError}
                </div>
              )}
              {successMessage && (
                <div className="rounded-xl border border-green-500/40 bg-green-500/10 px-3 py-2 text-xs text-green-600 dark:text-green-400">
                  {successMessage}
                </div>
              )}
              <div className="flex justify-between gap-2">
                <Button type="button" variant="ghost" onClick={resetForm} disabled={upsertTemplate.isPending}>
                  Reset
                </Button>
                <div className="flex gap-2">
                  {form.id && editingTemplate && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleDelete(editingTemplate)}
                      disabled={deleteTemplate.isPending}
                    >
                      Delete
                    </Button>
                  )}
                  <Button type="submit" disabled={upsertTemplate.isPending}>
                    {upsertTemplate.isPending ? 'Saving…' : form.id ? 'Update template' : 'Create template'}
                  </Button>
                </div>
              </div>
            </form>
          </section>

          <section className="space-y-3">
            <div className="rounded-2xl border border-border/60 bg-card/80 p-4">
              <p className="text-sm font-semibold text-foreground">Existing templates</p>
              <p className="text-xs text-muted-foreground">
                Select a template to edit or delete. Saving will refresh lists across the wizard.
              </p>
            </div>
            {isLoading ? (
              <div className="flex items-center gap-2 rounded-2xl border border-border/60 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                Loading…
              </div>
            ) : isError ? (
              <div className="space-y-2 rounded-2xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
                <p className="font-semibold">Unable to load templates</p>
                <p>{error instanceof Error ? error.message : 'Unknown error'}</p>
              </div>
            ) : templates.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/20 px-3 py-4 text-xs text-muted-foreground">
                No templates yet. Create one using the form on the left.
              </div>
            ) : (
              <ul className="space-y-2">
                {templates.map(template => (
                  <li key={template.id}>
                    <button
                      type="button"
                      onClick={() => handleEdit(template)}
                      className={cn(
                        'w-full rounded-2xl border border-border/60 bg-card/70 px-3 py-2 text-left text-xs transition hover:bg-muted/50',
                        template.id === form.id && 'ring-2 ring-primary/60',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="font-semibold text-foreground">{template.name}</p>
                          {template.description && (
                            <p className="text-muted-foreground">{template.description}</p>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-1">
                          {template.profile && (
                            <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                              {template.profile}
                            </Badge>
                          )}
                          {template.tags?.slice(0, 2).map(tag => (
                            <Badge key={`${template.id}-${tag}`} variant="outline" className="text-[10px]">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        Updated {new Date(template.updatedAt).toLocaleString()}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}
