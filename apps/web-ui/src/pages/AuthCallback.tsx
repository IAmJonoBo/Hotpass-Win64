import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function AuthCallback() {
  const navigate = useNavigate()
  const { completeLogin, isLoading } = useAuth()

  useEffect(() => {
    let isMounted = true
    completeLogin()
      .then(target => {
        if (!isMounted) return
        navigate(target ?? '/', { replace: true })
      })
      .catch(error => {
        console.error('Authentication callback failed', error)
        if (isMounted) {
          navigate('/', { replace: true })
        }
      })
    return () => {
      isMounted = false
    }
  }, [completeLogin, navigate])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Card className="max-w-md" role="status" aria-live="polite">
        <CardHeader>
          <CardTitle>Completing sign-in…</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {isLoading ? 'Finalising your session. This will only take a moment.' : 'Redirecting back to the dashboard.'}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
