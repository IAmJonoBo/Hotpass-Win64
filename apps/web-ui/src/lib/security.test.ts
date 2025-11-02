import { describe, expect, it, vi } from 'vitest'
import {
  clampText,
  createRateLimiter,
  sanitizeSearchTerm,
  sanitizeUrlInput,
} from './security'

describe('sanitizeSearchTerm', () => {
  it('removes unsafe characters and trims length', () => {
    const input = '  <script>alert(1)</script> hotpass  '
    const result = sanitizeSearchTerm(input, 12)
    expect(result).toBe('scriptal')
    expect(result.includes('<')).toBe(false)
    expect(result.length).toBeLessThanOrEqual(12)
  })
})

describe('sanitizeUrlInput', () => {
  it('accepts valid https URLs', () => {
    const result = sanitizeUrlInput(' https://example.com/api ')
    expect(result.valid).toBe(true)
    expect(result.value).toBe('https://example.com/api')
  })

  it('rejects unsupported protocols', () => {
    const result = sanitizeUrlInput('ftp://example.com')
    expect(result.valid).toBe(false)
    expect(result.reason).toMatch(/Only HTTP/)
  })
})

describe('clampText', () => {
  it('removes control characters and clamps to length', () => {
    const result = clampText('hello\u0007world', 5)
    expect(result).toBe('hello')
  })
})

describe('createRateLimiter', () => {
  it('enforces request spacing', async () => {
    vi.useFakeTimers()
    const limiter = createRateLimiter(1, 100)
    const timestamps: number[] = []

    const tasks = [0, 1, 2].map(() =>
      limiter(async () => {
        timestamps.push(Date.now())
      }),
    )

    await vi.advanceTimersByTimeAsync(500)
    await Promise.all(tasks)

    expect(timestamps).toHaveLength(3)
    expect(timestamps[1] - timestamps[0]).toBeGreaterThanOrEqual(100)
    expect(timestamps[2] - timestamps[1]).toBeGreaterThanOrEqual(100)
    vi.useRealTimers()
  })
})
