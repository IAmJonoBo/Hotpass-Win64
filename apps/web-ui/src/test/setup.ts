import '@testing-library/jest-dom/vitest'

if (typeof window !== 'undefined') {
  const { localStorage } = window
  if (!localStorage || typeof localStorage.clear !== 'function') {
    const store = new Map<string, string>()
    const mockStorage: Storage = {
      get length() {
        return store.size
      },
      clear: () => {
        store.clear()
      },
      getItem: (key: string) => store.get(key) ?? null,
      key: (index: number) => Array.from(store.keys())[index] ?? null,
      removeItem: (key: string) => {
        store.delete(key)
      },
      setItem: (key: string, value: string) => {
        store.set(key, value)
      },
    }

    Object.defineProperty(window, 'localStorage', {
      value: mockStorage,
      configurable: true,
    })
  }
}
