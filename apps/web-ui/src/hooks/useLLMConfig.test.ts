import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { fetchLLMConfig, useSelectedLLMProvider } from './useLLMConfig'

const sampleYaml = `
llm:
  strategy: preferred-first
  default: copilot
  providers:
    - name: copilot
      base_url: https://example.com
      models:
        - name: gpt-4o
          max_output_tokens: 8192
`

describe('fetchLLMConfig', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('parses provider configuration from YAML payload', async () => {
    const mockResponse = {
      ok: true,
      status: 200,
      text: vi.fn().mockResolvedValue(sampleYaml),
    } as unknown as Response
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    const config = await fetchLLMConfig()

    expect(global.fetch).toHaveBeenCalledWith('/config/llm-providers.yaml', { cache: 'no-store' })
    expect(config.strategy).toBe('preferred-first')
    expect(config.default).toBe('copilot')
    expect(config.providers).toHaveLength(1)
  })

  it('throws when the configuration request fails', async () => {
    const mockResponse = { ok: false, status: 503 } as unknown as Response
    global.fetch = vi.fn().mockResolvedValue(mockResponse)

    await expect(fetchLLMConfig()).rejects.toThrow(
      'Failed to load LLM provider configuration (503)',
    )
  })
})

describe('useSelectedLLMProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('prefers previously stored provider', () => {
    window.localStorage.setItem('hotpass_llm_provider', 'vertex')

    const { result } = renderHook(() => useSelectedLLMProvider({ default: 'copilot', providers: [], strategy: 'preferred-first' }))

    expect(result.current.selectedProvider).toBe('vertex')
  })

  it('updates localStorage when provider changes', () => {
    const { result } = renderHook(() =>
      useSelectedLLMProvider({ default: 'copilot', providers: [], strategy: 'preferred-first' }),
    )

    act(() => {
      result.current.setProvider('anthropic')
    })

    expect(result.current.selectedProvider).toBe('anthropic')
    expect(window.localStorage.getItem('hotpass_llm_provider')).toBe('anthropic')
  })
})
