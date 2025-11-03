const jsonHeaders: HeadersInit = {
  Accept: 'application/json',
}

let cachedToken: string | null = null

export async function ensureCsrfToken(force = false): Promise<string> {
  if (cachedToken && !force) {
    return cachedToken
  }

  const response = await fetch('/telemetry/operator-feedback/csrf', {
    method: 'GET',
    headers: jsonHeaders,
    credentials: 'include',
  })

  if (!response.ok) {
    throw new Error(`Failed to initialise CSRF token (${response.status})`)
  }

  const payload = (await response.json()) as { token?: string }
  if (!payload?.token) {
    throw new Error('Secure session token missing from response')
  }

  cachedToken = payload.token
  return cachedToken
}

export function invalidateCsrfToken(): void {
  cachedToken = null
}
