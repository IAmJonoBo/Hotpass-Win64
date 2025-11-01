import { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './AuthProvider'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

function LoadingState() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="status" aria-live="polite">
      <Card className="max-w-md">
        <CardHeader>
          <CardTitle>Checking access…</CardTitle>
          <CardDescription>Please wait while we validate your session.</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">This ensures restricted actions stay protected.</p>
        </CardContent>
      </Card>
    </div>
  )
}

function AccessDenied({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center" role="alert" aria-live="assertive">
      <Card className="max-w-md border-destructive/60">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            If you believe this is incorrect, contact an administrator to review your role assignments.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

interface RequireRoleProps {
  roles: string[]
  children: ReactNode
  fallback?: ReactNode
}

export function RequireRole({ roles, children, fallback }: RequireRoleProps) {
  const location = useLocation()
  const { isAuthenticated, isLoading, hasRole, login, storageReady } = useAuth()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      login().catch(error => console.error('Failed to initiate login', error))
    }
  }, [isLoading, isAuthenticated, login])

  if (isLoading || !storageReady) {
    return <LoadingState />
  }

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />
  }

  if (!hasRole(roles)) {
    if (fallback) {
      return <>{fallback}</>
    }
    return <AccessDenied title="Access restricted" description="You do not have permission to view this area." />
  }

  return <>{children}</>
}

interface RequireAuthProps {
  children: ReactNode
  fallback?: ReactNode
}

export function RequireAuth({ children, fallback }: RequireAuthProps) {
  const location = useLocation()
  const { isAuthenticated, isLoading, login } = useAuth()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      login().catch(error => console.error('Failed to initiate login', error))
    }
  }, [isAuthenticated, isLoading, login])

  if (isLoading) {
    return <LoadingState />
  }

  if (!isAuthenticated) {
    return fallback ? <>{fallback}</> : <Navigate to="/" state={{ from: location }} replace />
  }

  return <>{children}</>
}
