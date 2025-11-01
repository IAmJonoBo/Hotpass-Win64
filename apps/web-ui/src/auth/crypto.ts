const textEncoder = typeof TextEncoder !== 'undefined' ? new TextEncoder() : null

export async function deriveUserEncryptionKey(seed: string | undefined | null): Promise<CryptoKey | null> {
  if (!seed || typeof window === 'undefined' || !window.crypto?.subtle || !textEncoder) {
    return null
  }

  try {
    const data = textEncoder.encode(seed)
    const digest = await window.crypto.subtle.digest('SHA-256', data)
    return window.crypto.subtle.importKey(
      'raw',
      digest,
      { name: 'AES-GCM' },
      false,
      ['encrypt', 'decrypt'],
    )
  } catch (error) {
    console.error('Failed to derive encryption key', error)
    return null
  }
}
