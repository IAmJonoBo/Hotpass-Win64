import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import YAML from 'yaml'
import type { LLMConfig, LLMProvider } from '@/types/llm'

const CONFIG_URL = '/config/llm-providers.yaml'
const STORAGE_KEY = 'hotpass_llm_provider'

export async function fetchLLMConfig(): Promise<LLMConfig> {
  const response = await fetch(CONFIG_URL, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Failed to load LLM provider configuration (${response.status})`)
  }
  const text = await response.text()
  const parsed = YAML.parse(text) as { llm?: Partial<LLMConfig> & { providers?: LLMProvider[] } }
  const llm = parsed.llm ?? {}

  return {
    strategy: llm.strategy ?? 'cheapest-first',
    default: llm.default ?? (llm.providers?.[0]?.name ?? 'copilot'),
    providers: llm.providers ?? [],
  }
}

export function useLLMConfig() {
  return useQuery({
    queryKey: ['llm-config'],
    queryFn: fetchLLMConfig,
    staleTime: 1000 * 60 * 10,
  })
}

export function useSelectedLLMProvider(config?: LLMConfig) {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) {
      setSelectedProvider(stored)
    } else if (config?.default) {
      setSelectedProvider(config.default)
    }
  }, [config?.default])

  const updateProvider = (providerName: string) => {
    if (typeof window === 'undefined') return
    setSelectedProvider(providerName)
    window.localStorage.setItem(STORAGE_KEY, providerName)
  }

  return {
    selectedProvider,
    setProvider: updateProvider,
  }
}
