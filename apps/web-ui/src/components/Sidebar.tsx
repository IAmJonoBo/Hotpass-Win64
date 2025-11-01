import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  Settings,
  Activity,
  Moon,
  Sun,
  MessageSquare,
  History,
  Stethoscope,
} from 'lucide-react'
import { cn, getEnvironmentColor } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useState, useEffect } from 'react'
import { useAuth } from '@/auth'

interface SidebarProps {
  environment?: string
  onOpenAssistant?: (message?: string) => void
  onOpenActivity?: () => void
}

export function Sidebar({ environment = 'local', onOpenAssistant, onOpenActivity }: SidebarProps) {
  const [darkMode, setDarkMode] = useState(() => {
    // Check localStorage or default to dark mode
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('darkMode')
      return stored ? JSON.parse(stored) : true
    }
    return true
  })

  useEffect(() => {
    // Apply dark mode class to document
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    // Save preference
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
  }, [darkMode])

  const { user, isAuthenticated, isLoading, login, logout, hasRole } = useAuth()

  const navigation: Array<{
    name: string
    href: string
    icon: typeof LayoutDashboard
    roles?: readonly string[]
  }> = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Lineage', href: '/lineage', icon: GitBranch },
    { name: 'Health', href: '/health', icon: Stethoscope },
    { name: 'Assistant', href: '/assistant', icon: MessageSquare },
    { name: 'Admin', href: '/admin', icon: Settings, roles: ['admin'] as const },
  ]

  const filteredNavigation = navigation.filter(item => {
    if (!('roles' in item) || !item.roles) return true
    return item.roles.some(role => hasRole(role))
  })

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card">
      {/* Logo and environment badge */}
      <div className="flex items-center justify-between p-6">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-xl font-bold">Hotpass</h1>
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-full",
              getEnvironmentColor(environment)
            )}>
              {environment}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3">
        {filteredNavigation.map(item => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.name}
          </NavLink>
        ))}
      </nav>

      {/* Dark mode toggle and Assistant button */}
      <div className="border-t p-4 space-y-2">
        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
          <span aria-live="polite">
            {isAuthenticated && user
              ? `Signed in as ${user.name || user.email || user.id}`
              : 'Not signed in'}
          </span>
        </div>
        {onOpenActivity && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenActivity()}
            className="w-full justify-start"
          >
            <History className="mr-2 h-4 w-4" />
            Agent Activity
          </Button>
        )}
        {onOpenAssistant && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenAssistant()}
            className="w-full justify-start"
          >
            <MessageSquare className="mr-2 h-4 w-4" />
            Open Assistant
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setDarkMode(!darkMode)}
          className="w-full justify-start"
        >
          {darkMode ? (
            <>
              <Sun className="mr-2 h-4 w-4" />
              Light Mode
            </>
          ) : (
            <>
              <Moon className="mr-2 h-4 w-4" />
              Dark Mode
            </>
          )}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading}
          onClick={() => {
            if (isAuthenticated) {
              void logout()
            } else {
              void login()
            }
          }}
          className="w-full justify-start"
        >
          {isAuthenticated ? 'Sign out' : 'Sign in'}
        </Button>
      </div>

      {/* Footer */}
      <div className="border-t p-4 text-xs text-muted-foreground">
        <p>Hotpass v0.1.0</p>
        <p className="mt-1">Data Pipeline Dashboard</p>
      </div>
    </div>
  )
}
