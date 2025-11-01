/**
 * Security utilities for client-side hardening (input sanitisation, rate limiting, etc.).
 */

export interface SanitisedUrlResult {
  value: string
  valid: boolean
  reason?: string
}

const SAFE_SEARCH_PATTERN = /[^\w\s:/@.-]/gu
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/gu

export function sanitizeSearchTerm(input: string, maxLength = 120): string {
  if (!input) return ''
  const trimmed = input.slice(0, maxLength)
  return trimmed.replace(CONTROL_CHARS, '').replace(SAFE_SEARCH_PATTERN, '').trim()
}

export function sanitizeUrlInput(raw: string, { allowEmpty = true }: { allowEmpty?: boolean } = {}): SanitisedUrlResult {
  const value = raw.trim().replace(CONTROL_CHARS, '')
  if (!value) {
    return allowEmpty
      ? { value: '', valid: true }
      : { value: '', valid: false, reason: 'URL is required.' }
  }
  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol)) {
      return { value, valid: false, reason: 'Only HTTP/HTTPS URLs are supported.' }
    }
    if (url.username || url.password) {
      return { value, valid: false, reason: 'Credentials must not be embedded in URLs.' }
    }
    const normalised = url.href.replace(/\/$/, '')
    if (normalised.length > 2048) {
      return { value: normalised, valid: false, reason: 'URL is too long.' }
    }
    return { value: normalised, valid: true }
  } catch (error) {
    return { value, valid: false, reason: 'Invalid URL format.' }
  }
}

export function clampText(input: string, maxLength = 500): string {
  if (!input) return ''
  return input.replace(CONTROL_CHARS, '').slice(0, maxLength)
}

type RateLimitedTask<T> = () => Promise<T>

type QueueTask<T> = {
  run: () => void
  resolve: (value: T | PromiseLike<T>) => void
  reject: (reason?: unknown) => void
}

export function createRateLimiter(maxRequests: number, intervalMs: number) {
  if (maxRequests < 1) {
    throw new Error('maxRequests must be >= 1')
  }
  const queue: QueueTask<unknown>[] = []
  const timestamps: number[] = []

  function prune(now: number) {
    while (timestamps.length && now - timestamps[0] >= intervalMs) {
      timestamps.shift()
    }
  }

  function schedule<T>(task: RateLimitedTask<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const queued: QueueTask<T> = {
        run: async () => {
          try {
            const now = Date.now()
            prune(now)
            if (timestamps.length >= maxRequests) {
              const wait = intervalMs - (now - timestamps[0])
              setTimeout(() => {
                queue.unshift(queued as unknown as QueueTask<unknown>)
                processQueue()
              }, Math.max(wait, 0))
              return
            }
            timestamps.push(Date.now())
            const result = await task()
            resolve(result)
          } catch (error) {
            reject(error)
          } finally {
            const nowDone = Date.now()
            prune(nowDone)
            setTimeout(processQueue, 0)
          }
        },
        resolve,
        reject,
      }
      queue.push(queued as QueueTask<unknown>)
      processQueue()
    })
  }

  function processQueue() {
    if (!queue.length) return
    const now = Date.now()
    prune(now)
    if (timestamps.length >= maxRequests) {
      const wait = intervalMs - (now - timestamps[0])
      setTimeout(processQueue, Math.max(wait, 0))
      return
    }
    const next = queue.shift()
    if (next) {
      next.run()
    }
  }

  return schedule
}
