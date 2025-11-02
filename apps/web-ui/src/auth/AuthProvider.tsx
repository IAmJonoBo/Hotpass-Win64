import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'
import { jwtDecode } from 'jwt-decode'
import { deriveUserEncryptionKey } from './crypto'
import { setHilSecurityContext } from '@/lib/secureStorage'

type MaybeArray<T> = T | T[]

type AuthUser = {
  id: string
  email?: string
  name?: string
  givenName?: string
  familyName?: string
  roles: string[]
  raw?: User | null
}

interface AuthContextValue {
  user: AuthUser | null
  roles: string[]
  isAuthenticated: boolean
  isLoading: boolean
  storageReady: boolean
  login: () => Promise<void>
  logout: () => Promise<void>
  completeLogin: () => Promise<string | undefined>
  getAccessToken: () => Promise<string | null>
  hasRole: (roles: MaybeArray<string>) => boolean
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const runtimeOrigin = typeof window !== 'undefined' ? window.location.origin : ''
const oidcAuthority = import.meta.env.VITE_OIDC_AUTHORITY || import.meta.env.HOTPASS_OIDC_AUTHORITY
const oidcClientId = import.meta.env.VITE_OIDC_CLIENT_ID || import.meta.env.HOTPASS_OIDC_CLIENT_ID
const oidcRedirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI || (runtimeOrigin ? `${runtimeOrigin}/auth/callback` : '/auth/callback')
const oidcScopes = import.meta.env.VITE_OIDC_SCOPES || 'openid profile email'
const oidcPostLogoutRedirect = import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT || runtimeOrigin || '/'
const envAuthDisabled = import.meta.env.VITE_AUTH_DISABLED === 'true'
const authDisabled = envAuthDisabled || !oidcAuthority || !oidcClientId

if (authDisabled && !envAuthDisabled) {
  console.warn('OIDC authority/client id not configured; running in mock auth mode.')
}

function resolveMockRoles(): string[] {
  const stored = typeof window !== 'undefined' ? window.localStorage.getItem('hotpass_mock_roles') : null
  const source = stored || import.meta.env.VITE_AUTH_MOCK_ROLES || 'admin,operator,approver'
  return source
    .split(',')
    .map((role: string) => role.trim().toLowerCase())
    .filter(Boolean)
}

function normaliseRoles(input: unknown): string[] {
  if (!input) return []
  if (Array.isArray(input)) {
    return input.map((role: unknown) => String(role).toLowerCase())
  }
  if (typeof input === 'string') {
    return input.split(',').map(role => role.trim().toLowerCase()).filter(Boolean)
  }
  return []
}

function extractRoles(user: User | null): string[] {
  if (!user) return []
  const claims: Record<string, unknown> = { ...user.profile }
  try {
    if (user.id_token) {
      const decoded = jwtDecode<Record<string, unknown>>(user.id_token)
      Object.assign(claims, decoded)
    }
  } catch (error) {
    console.warn('Failed to decode ID token for roles', error)
  }

  const candidateKeys = [
    'roles',
    'groups',
    'role',
    'app_roles',
    'https://schemas.okta.com/roles',
    'https://hotpass.dev/roles',
  ]

  const collected = new Set<string>()
  for (const key of candidateKeys) {
    const value = claims[key]
    normaliseRoles(value).forEach(role => collected.add(role))
  }

  return Array.from(collected)
}

function buildAuthUser(user: User | null): AuthUser | null {
  if (!user) return null
  const roles = extractRoles(user)
  const preferredUsername = typeof user.profile.preferred_username === 'string' ? user.profile.preferred_username : undefined
  const email = typeof user.profile.email === 'string' ? user.profile.email : undefined
  const sub = typeof user.profile.sub === 'string' ? user.profile.sub : user.profile.sid

  const id = sub || preferredUsername || email || user.profile.name || user.profile.nonce || 'unknown-user'

  return {
    id,
    email,
    name: typeof user.profile.name === 'string' ? user.profile.name : preferredUsername || email,
    givenName: typeof user.profile.given_name === 'string' ? user.profile.given_name : undefined,
    familyName: typeof user.profile.family_name === 'string' ? user.profile.family_name : undefined,
    roles,
    raw: user,
  }
}

function createUserManager(): UserManager | null {
  if (authDisabled) {
    return null
  }
  return new UserManager({
    authority: oidcAuthority,
    client_id: oidcClientId,
    redirect_uri: oidcRedirectUri,
    post_logout_redirect_uri: oidcPostLogoutRedirect,
    response_type: 'code',
    scope: oidcScopes,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true,
  })
}

let userManager: UserManager | null | undefined

function getManager(): UserManager | null {
  if (userManager === undefined) {
    userManager = createUserManager()
  }
  return userManager ?? null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [storageReady, setStorageReady] = useState(false)

  const initialiseSecureStorage = useCallback(async (nextUser: AuthUser | null) => {
    if (!nextUser) {
      setHilSecurityContext({ userId: null, key: null })
      setStorageReady(false)
      return
    }

    let seed: string | null = null
    if (authDisabled) {
      seed = `${nextUser.id}-dev-seed`
    } else {
      const manager = getManager()
      seed = nextUser.raw?.id_token ?? manager?.settings?.client_id ?? nextUser.id
    }

    const key = await deriveUserEncryptionKey(seed)
    if (!key) {
      console.warn('Unable to initialise encryption key; secure storage disabled')
      setHilSecurityContext({ userId: nextUser.id, key: null })
      setStorageReady(true)
      return
    }
    setHilSecurityContext({ userId: nextUser.id, key })
    setStorageReady(true)
  }, [])

  useEffect(() => {
    if (authDisabled) {
      const mockUser: AuthUser = {
        id: 'mock-user',
        email: 'mock.user@example.com',
        name: 'Mock User',
        roles: resolveMockRoles(),
      }
      setUser(mockUser)
      initialiseSecureStorage(mockUser).catch(console.error)
      setStorageReady(true)
      setIsLoading(false)
      return
    }

    const manager = getManager()
    if (!manager) {
      setUser(null)
      setIsLoading(false)
      return
    }

    let active = true

    manager
      .getUser()
      .then(current => {
        if (!active) return
        const authUser = buildAuthUser(current)
        setUser(authUser)
        initialiseSecureStorage(authUser).catch(console.error)
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })

    const handleUserLoaded = (loaded: User) => {
      const authUser = buildAuthUser(loaded)
      setUser(authUser)
      initialiseSecureStorage(authUser).catch(console.error)
    }
    const handleUserUnloaded = () => {
      setUser(null)
      initialiseSecureStorage(null).catch(console.error)
    }

    manager.events.addUserLoaded(handleUserLoaded)
    manager.events.addUserUnloaded(handleUserUnloaded)

    return () => {
      active = false
      manager.events.removeUserLoaded(handleUserLoaded)
      manager.events.removeUserUnloaded(handleUserUnloaded)
    }
  }, [initialiseSecureStorage])

  const login = useCallback(async () => {
    if (authDisabled) {
      const mockUser: AuthUser = {
        id: 'mock-user',
        email: 'mock.user@example.com',
        name: 'Mock User',
        roles: resolveMockRoles(),
      }
      setUser(mockUser)
      setStorageReady(true)
      setIsLoading(false)
      return
    }
    const manager = getManager()
    if (!manager) {
      throw new Error('OIDC configuration missing. Cannot log in.')
    }
    await manager.signinRedirect({ state: window.location.pathname + window.location.search })
  }, [])

  const logout = useCallback(async () => {
    if (authDisabled) {
      setUser(null)
      setStorageReady(false)
      return
    }
    const manager = getManager()
    if (!manager) {
      setUser(null)
      setStorageReady(false)
      return
    }
    await manager.signoutRedirect({ state: window.location.origin })
  }, [])

  const completeLogin = useCallback(async () => {
    if (authDisabled) {
      return '/'
    }
    const manager = getManager()
    if (!manager) {
      return '/'
    }
    const authenticated = await manager.signinRedirectCallback()
    const authUser = buildAuthUser(authenticated)
    setUser(authUser)
    await initialiseSecureStorage(authUser)
    const state = authenticated?.state
    if (typeof state === 'string' && state.startsWith('/')) {
      return state
    }
    if (state && typeof (state as { returnUrl?: string }).returnUrl === 'string') {
      return (state as { returnUrl?: string }).returnUrl
    }
    return '/'
  }, [initialiseSecureStorage])

  const getAccessToken = useCallback(async () => {
    if (authDisabled) {
      return null
    }
    const manager = getManager()
    if (!manager) {
      return null
    }
    const current = await manager.getUser()
    return current?.access_token ?? null
  }, [])

  const roles = useMemo(() => user?.roles ?? [], [user?.roles])

  const hasRole = useCallback(
    (roleOrRoles: MaybeArray<string>) => {
      if (!roleOrRoles) return false
      const list = Array.isArray(roleOrRoles) ? roleOrRoles : [roleOrRoles]
      const lowered = list.map(role => role.toLowerCase())
      return lowered.some(role => roles.includes(role))
    },
    [roles],
  )

  const value = useMemo<AuthContextValue>(() => ({
    user,
    roles,
    isAuthenticated: Boolean(user),
    isLoading,
    storageReady,
    login,
    logout,
    completeLogin,
    getAccessToken,
    hasRole,
  }), [user, roles, isLoading, storageReady, login, logout, completeLogin, getAccessToken, hasRole])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
