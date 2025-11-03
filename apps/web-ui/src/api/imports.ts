import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRateLimiter } from '@/lib/security'
import type {
  ImportProfile,
  ImportTemplate,
  ImportTemplatePayload,
  StoredImportProfile,
  CommandJob,
} from '@/types'
import { ensureCsrfToken } from './csrf'

const BASE_PATH = '/api/imports'
const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

const fetchLimiter = createRateLimiter(10, 30_000)

const limitedFetch = <T = unknown>(input: RequestInfo | URL, init: RequestInit = {}): Promise<T> =>
  fetchLimiter(async () => {
    const response = await fetch(input, {
      credentials: 'include',
      ...init,
      headers: {
        ...jsonHeaders,
        ...(init.headers ?? {}),
      },
    })
    if (!response.ok) {
      let message = response.statusText || 'Request failed'
      try {
        const payload = await response.json()
        if (payload && typeof payload.error === 'string') {
          message = payload.error
        }
      } catch {
        // ignore parse errors
      }
      throw new Error(message)
    }
    const contentType = response.headers.get('Content-Type') ?? ''
    if (contentType.includes('application/json')) {
      return response.json() as Promise<T>
    }
    return undefined as T
  })

export interface ProfileWorkbookParams {
  file?: File
  workbookPath?: string
  sampleRows?: number
  maxRows?: number
  signal?: AbortSignal
}

export interface ProfileWorkbookResponse {
  profile: ImportProfile
}

export async function profileWorkbook({
  file,
  workbookPath,
  sampleRows,
  maxRows,
  signal,
}: ProfileWorkbookParams): Promise<ImportProfile> {
  if (!file && !workbookPath) {
    throw new Error('Provide either a workbook File or workbookPath')
  }

  const params = new URLSearchParams()
  if (Number.isFinite(sampleRows)) {
    params.set('sampleRows', String(sampleRows))
  }
  if (Number.isFinite(maxRows)) {
    params.set('maxRows', String(maxRows))
  }
  const endpoint = `${BASE_PATH}/profile${params.size ? `?${params.toString()}` : ''}`

  if (file) {
    const formData = new FormData()
    formData.append('file', file, file.name || 'workbook.xlsx')
    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
      credentials: 'include',
      signal,
    })
    if (!response.ok) {
      const message = await extractErrorMessage(response)
      throw new Error(message)
    }
    const payload = await response.json() as ProfileWorkbookResponse
    return payload.profile
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    body: JSON.stringify({ workbookPath }),
    headers: {
      ...jsonHeaders,
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal,
  })
  if (!response.ok) {
    const message = await extractErrorMessage(response)
    throw new Error(message)
  }
  const payload = await response.json() as ProfileWorkbookResponse
  return payload.profile
}

export interface ListStoredProfilesResponse {
  profiles: StoredImportProfile[]
}

export const importsApi = {
  profileWorkbook,

  async listStoredProfiles(): Promise<StoredImportProfile[]> {
    const payload = await limitedFetch<ListStoredProfilesResponse>(`${BASE_PATH}/profiles`)
    return Array.isArray(payload?.profiles) ? payload.profiles : []
  },

  async deleteStoredProfile(profileId: string): Promise<void> {
    const token = await ensureCsrfToken()
    const response = await fetch(`${BASE_PATH}/profiles/${encodeURIComponent(profileId)}`, {
      method: 'DELETE',
      headers: {
        ...jsonHeaders,
        'X-CSRF-Token': token,
      },
      credentials: 'include',
    })
    if (!response.ok) {
      const message = await extractErrorMessage(response)
      throw new Error(message)
    }
  },

  async listTemplates(): Promise<ImportTemplate[]> {
    const payload = await limitedFetch<{ templates?: ImportTemplate[] }>(`${BASE_PATH}/templates`)
    return Array.isArray(payload?.templates) ? payload.templates : []
  },

  async getTemplate(templateId: string): Promise<ImportTemplate> {
    return limitedFetch<ImportTemplate>(`${BASE_PATH}/templates/${encodeURIComponent(templateId)}`)
  },

  async upsertTemplate(
    input: {
      id?: string
      name: string
      description?: string
      profile?: string
      tags?: string[]
      payload: ImportTemplatePayload
    },
  ): Promise<ImportTemplate> {
    const token = await ensureCsrfToken()
    const method = input.id ? 'PUT' : 'POST'
    const endpoint = input.id
      ? `${BASE_PATH}/templates/${encodeURIComponent(input.id)}`
      : `${BASE_PATH}/templates`

    const response = await fetch(endpoint, {
      method,
      headers: {
        ...jsonHeaders,
        'Content-Type': 'application/json',
        'X-CSRF-Token': token,
      },
      credentials: 'include',
      body: JSON.stringify(input),
    })
    if (!response.ok) {
      const message = await extractErrorMessage(response)
      throw new Error(message)
    }
    return response.json() as Promise<ImportTemplate>
  },

  async deleteTemplate(templateId: string): Promise<void> {
    const token = await ensureCsrfToken()
    const response = await fetch(`${BASE_PATH}/templates/${encodeURIComponent(templateId)}`, {
      method: 'DELETE',
      headers: {
        ...jsonHeaders,
        'X-CSRF-Token': token,
      },
      credentials: 'include',
    })
    if (!response.ok) {
      const message = await extractErrorMessage(response)
      throw new Error(message)
    }
  },

  async getTemplateSummary(templateId: string) {
    return limitedFetch<{ template: ImportTemplate; summary: Record<string, unknown>; consolidation: Record<string, unknown> }>(`${BASE_PATH}/templates/${encodeURIComponent(templateId)}/summary`)
  },

  async publishTemplateContract(templateId: string, options?: { format?: 'yaml' | 'json' }) {
    const token = await ensureCsrfToken()
    const response = await fetch(`${BASE_PATH}/templates/${encodeURIComponent(templateId)}/contracts`, {
      method: 'POST',
      headers: {
        ...jsonHeaders,
        'Content-Type': 'application/json',
        'X-CSRF-Token': token,
      },
      credentials: 'include',
      body: JSON.stringify({ format: options?.format ?? 'yaml' }),
    })
    if (!response.ok) {
      const message = await extractErrorMessage(response)
      throw new Error(message)
    }
    return response.json() as Promise<{ job: CommandJob }>
  },

  async getConsolidationTelemetry() {
    return limitedFetch<{ aggregate: Record<string, unknown>; templates: Array<Record<string, unknown>> }>(`${BASE_PATH}/consolidation/telemetry`)
  },
}

async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (payload && typeof payload.error === 'string') {
      return payload.error
    }
  } catch {
    // ignore parse errors
  }
  return response.statusText || 'Request failed'
}

export function useImportProfileMutation() {
  return useMutation({
    mutationKey: ['imports', 'profile'],
    mutationFn: profileWorkbook,
  })
}

export function useStoredImportProfiles() {
  return useQuery({
    queryKey: ['imports', 'profiles'],
    queryFn: () => importsApi.listStoredProfiles(),
    staleTime: 60_000,
  })
}

export function useImportTemplates() {
  return useQuery({
    queryKey: ['imports', 'templates'],
    queryFn: () => importsApi.listTemplates(),
    staleTime: 60_000,
  })
}

export function useImportTemplateUpsert() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: ['imports', 'template-upsert'],
    mutationFn: importsApi.upsertTemplate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['imports', 'templates'] })
    },
  })
}

export function useImportTemplateDelete() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: ['imports', 'template-delete'],
    mutationFn: importsApi.deleteTemplate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['imports', 'templates'] })
    },
  })
}

export function useTemplateSummary(templateId: string | null) {
  return useQuery({
    queryKey: ['imports', 'template-summary', templateId],
    enabled: Boolean(templateId),
    queryFn: () => importsApi.getTemplateSummary(templateId as string),
    staleTime: 60_000,
  })
}

export function usePublishTemplateContract() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: ['imports', 'publish-contract'],
    mutationFn: ({ templateId, format }: { templateId: string; format?: 'yaml' | 'json' }) =>
      importsApi.publishTemplateContract(templateId, { format }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contracts'] })
    },
  })
}

export function useConsolidationTelemetry() {
  return useQuery({
    queryKey: ['imports', 'consolidation-telemetry'],
    queryFn: () => importsApi.getConsolidationTelemetry(),
    staleTime: 60_000,
  })
}
