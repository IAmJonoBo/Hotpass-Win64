/**
 * Admin Page
 *
 * Configuration interface for:
 * - Prefect API URL and key
 * - Marquez/OpenLineage API URL
 * - Environment settings
 *
 * Settings are persisted to localStorage
 */

import { useState, useEffect, type ChangeEvent } from 'react'
import { Save, Check, AlertCircle, Loader2, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LLMProviderSelector } from '@/components/settings/LLMProviderSelector'
import { getRetentionPolicy, applyRetentionImmediately } from '@/lib/secureStorage'
import { setHilRetentionPolicy, type HilRetentionPolicy } from '@/lib/hilRetention'
import { sanitizeUrlInput } from '@/lib/security'

interface ConfigSettings {
  prefectApiUrl: string
  marquezApiUrl: string
  environment: 'local' | 'staging' | 'prod'
  telemetryEnabled: boolean
}

const DEFAULT_SETTINGS: ConfigSettings = {
  prefectApiUrl:
    import.meta.env.PREFECT_API_URL ||
    import.meta.env.VITE_PREFECT_API_URL ||
    'http://localhost:4200',
  marquezApiUrl:
    import.meta.env.OPENLINEAGE_URL ||
    import.meta.env.VITE_MARQUEZ_API_URL ||
    'http://localhost:5000',
  environment:
    (import.meta.env.HOTPASS_ENVIRONMENT as ConfigSettings['environment']) ||
    (import.meta.env.VITE_ENVIRONMENT as ConfigSettings['environment']) ||
    'local',
  telemetryEnabled: true,
}

export function Admin() {
  const [settings, setSettings] = useState<ConfigSettings>(DEFAULT_SETTINGS)
  const [saved, setSaved] = useState(false)
  const [testingConnection, setTestingConnection] = useState<{
    prefect: boolean
    marquez: boolean
  }>({ prefect: false, marquez: false })
  const [connectionStatus, setConnectionStatus] = useState<{
    prefect: 'unknown' | 'success' | 'error'
    marquez: 'unknown' | 'success' | 'error'
  }>({ prefect: 'unknown', marquez: 'unknown' })
  const [retentionPolicy, setRetentionPolicy] = useState<HilRetentionPolicy>(() => getRetentionPolicy())
  const [errors, setErrors] = useState<{ prefectApiUrl?: string; marquezApiUrl?: string }>({})

  // Load settings from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('hotpass_config')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setSettings({ ...DEFAULT_SETTINGS, ...parsed })
      } catch (error) {
        console.error('Failed to parse stored config:', error)
      }
    }
  }, [])

  useEffect(() => {
    setRetentionPolicy(getRetentionPolicy())
  }, [])

  const hasActiveErrors = Object.values(errors).some(Boolean)

  const handleSave = () => {
    if (hasActiveErrors) {
      return
    }
    // Save to localStorage
    localStorage.setItem('hotpass_config', JSON.stringify(settings))
    localStorage.setItem('hotpass_environment', settings.environment)

    setSaved(true)
    setTimeout(() => setSaved(false), 2000)

    // In a real implementation, you might also want to reload the page
    // or update a global config context
  }

  const setUrlValue = (field: 'prefectApiUrl' | 'marquezApiUrl', value: string) => {
    const sanitised = sanitizeUrlInput(value, { allowEmpty: false })
    setSettings(prev => ({ ...prev, [field]: sanitised.value }))
    setErrors(prev => ({ ...prev, [field]: sanitised.valid ? undefined : sanitised.reason }))
  }

  const testConnection = async (type: 'prefect' | 'marquez') => {
    const field = type === 'prefect' ? 'prefectApiUrl' : 'marquezApiUrl'
    if (errors[field]) {
      return
    }
    setTestingConnection(prev => ({ ...prev, [type]: true }))

    try {
      const url = type === 'prefect' ? settings.prefectApiUrl : settings.marquezApiUrl
      const sanitised = sanitizeUrlInput(url, { allowEmpty: false })
      if (!sanitised.valid) {
        setErrors(prev => ({ ...prev, [field]: sanitised.reason }))
        return
      }
      const testEndpoint = type === 'prefect'
        ? `${sanitised.value}/health`
        : `${sanitised.value}/api/v1/namespaces`

      const response = await fetch(testEndpoint, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      })

      if (response.ok) {
        setConnectionStatus(prev => ({ ...prev, [type]: 'success' }))
      } else {
        setConnectionStatus(prev => ({ ...prev, [type]: 'error' }))
      }
    } catch {
      setConnectionStatus(prev => ({ ...prev, [type]: 'error' }))
    } finally {
      setTestingConnection(prev => ({ ...prev, [type]: false }))
    }
  }

  const handleRetentionToggle = async (event: ChangeEvent<HTMLInputElement>) => {
    await handleRetentionChange({ ...retentionPolicy, enabled: event.target.checked })
  }

  const handleRetentionDays = async (event: ChangeEvent<HTMLInputElement>) => {
    const nextDays = Number.parseInt(event.target.value, 10)
    if (Number.isNaN(nextDays) || nextDays < 1) {
      return
    }
    await handleRetentionChange({ ...retentionPolicy, days: nextDays })
  }

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS)
    localStorage.removeItem('hotpass_config')
    localStorage.removeItem('hotpass_environment')
    setConnectionStatus({ prefect: 'unknown', marquez: 'unknown' })
    const policy = getRetentionPolicy()
    setRetentionPolicy(policy)
  }

  const handleRetentionChange = async (policy: HilRetentionPolicy) => {
    setRetentionPolicy(policy)
    setHilRetentionPolicy(policy)
    await applyRetentionImmediately()
  }

  useEffect(() => {
    // Kick off an optimistic health check so the header can enumerate connection state.
    testConnection('prefect')
    testConnection('marquez')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const getStatusMeta = (status: 'unknown' | 'success' | 'error', isTesting: boolean) => {
    if (isTesting) {
      return {
        label: 'Checking…',
        className: 'border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300',
        icon: <Loader2 className="mr-1 h-3 w-3 animate-spin" />,
      }
    }
    switch (status) {
      case 'success':
        return {
          label: 'Connected',
          className: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
          icon: <Check className="mr-1 h-3 w-3" />,
        }
      case 'error':
        return {
          label: 'Unreachable',
          className: 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400',
          icon: <XCircle className="mr-1 h-3 w-3" />,
        }
      default:
        return {
          label: 'Unknown',
          className: 'border-muted text-muted-foreground',
          icon: <AlertCircle className="mr-1 h-3 w-3" />,
        }
    }
  }

  const prefectMeta = getStatusMeta(connectionStatus.prefect, testingConnection.prefect)
  const marquezMeta = getStatusMeta(connectionStatus.marquez, testingConnection.marquez)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Admin Settings</h1>
            <p className="text-muted-foreground">
              Configure API endpoints and environment settings
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={`flex items-center gap-1 ${prefectMeta.className}`}>
              {prefectMeta.icon}
              Prefect: {prefectMeta.label}
            </Badge>
            <Badge variant="outline" className={`flex items-center gap-1 ${marquezMeta.className}`}>
              {marquezMeta.icon}
              Marquez: {marquezMeta.label}
            </Badge>
          </div>
        </div>
      </div>

      {/* Alert - Settings are local */}
      <Card className="border-yellow-500/50 bg-yellow-500/10">
        <CardContent className="flex items-start gap-3 pt-6">
          <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold text-sm">Local Configuration</div>
            <p className="text-xs text-muted-foreground mt-1">
              Settings are stored in your browser's localStorage. They will not sync across devices
              or be shared with other users.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* LLM Provider Selector */}
      <LLMProviderSelector />

      {/* HIL Retention Policy */}
      <Card>
        <CardHeader>
          <CardTitle>Human-in-the-loop retention</CardTitle>
          <CardDescription>
            Secure approvals are stored in encrypted IndexedDB. Control how long audit entries are retained per operator.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium" htmlFor="hil-retention-enabled">
              Enable retention policy
            </label>
            <input
              id="hil-retention-enabled"
              type="checkbox"
              className="h-4 w-4"
              checked={retentionPolicy.enabled}
              onChange={handleRetentionToggle}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="hil-retention-days">
              Retention window (days)
            </label>
            <Input
              id="hil-retention-days"
              type="number"
              min={1}
              value={retentionPolicy.days}
              onChange={handleRetentionDays}
              disabled={!retentionPolicy.enabled}
            />
            <p className="text-xs text-muted-foreground">
              Older approvals are securely purged once this window expires. Adjust to align with your compliance posture.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Environment Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Environment</CardTitle>
          <CardDescription>
            Select the current environment for proper labeling and behavior
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Current Environment</label>
            <div className="flex gap-2">
              {(['local', 'staging', 'prod'] as const).map((env) => (
                <Button
                  key={env}
                  variant={settings.environment === env ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSettings({ ...settings, environment: env })}
                >
                  {env === 'prod' ? 'Production' : env.charAt(0).toUpperCase() + env.slice(1)}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Prefect API Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Prefect API</CardTitle>
          <CardDescription>
            Configure connection to Prefect Cloud or Server for flow run data
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label htmlFor="prefectUrl" className="text-sm font-medium mb-2 block">
              API URL
            </label>
            <Input
              id="prefectUrl"
              type="url"
              placeholder="http://localhost:4200"
              value={settings.prefectApiUrl}
              onChange={(e) => setUrlValue('prefectApiUrl', e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Base URL for the Prefect API (e.g., http://localhost:4200 or https://api.prefect.cloud)
            </p>
            {errors.prefectApiUrl && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400" role="alert">
                {errors.prefectApiUrl}
              </p>
            )}
            {settings.prefectApiUrl.includes('.internal') && (
              <div className="mt-2 bg-yellow-500/10 border border-yellow-500/20 rounded p-2 text-xs">
                <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 font-medium">
                  <AlertCircle className="h-3 w-3" />
                  VPC/Internal URL Detected
                </div>
                <p className="text-muted-foreground mt-1">
                  This URL appears to be in a private VPC. Make sure you're connected via VPN or
                  bastion tunnel before testing the connection.
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => testConnection('prefect')}
              disabled={testingConnection.prefect}
            >
              {testingConnection.prefect ? 'Testing...' : 'Test Connection'}
            </Button>
            {connectionStatus.prefect === 'success' && (
              <Badge variant="outline" className="text-green-600 dark:text-green-400">
                <Check className="h-3 w-3 mr-1" />
                Connected
              </Badge>
            )}
            {connectionStatus.prefect === 'error' && (
              <Badge variant="outline" className="text-red-600 dark:text-red-400">
                <AlertCircle className="h-3 w-3 mr-1" />
                Failed
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Marquez API Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Marquez / OpenLineage API</CardTitle>
          <CardDescription>
            Configure connection to Marquez backend for lineage data
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label htmlFor="marquezUrl" className="text-sm font-medium mb-2 block">
              API URL
            </label>
            <Input
              id="marquezUrl"
              type="url"
              placeholder="http://localhost:5000"
              value={settings.marquezApiUrl}
              onChange={(e) => setUrlValue('marquezApiUrl', e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Base URL for the Marquez API (e.g., http://localhost:5000 or https://marquez.staging.internal)
            </p>
            {errors.marquezApiUrl && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400" role="alert">
                {errors.marquezApiUrl}
              </p>
            )}
            {settings.marquezApiUrl.includes('.internal') && (
              <div className="mt-2 bg-yellow-500/10 border border-yellow-500/20 rounded p-2 text-xs">
                <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400 font-medium">
                  <AlertCircle className="h-3 w-3" />
                  VPC/Internal URL Detected
                </div>
                <p className="text-muted-foreground mt-1">
                  This URL appears to be in a private VPC. Make sure you're connected via VPN or
                  bastion tunnel before testing the connection.
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => testConnection('marquez')}
              disabled={testingConnection.marquez}
            >
              {testingConnection.marquez ? 'Testing...' : 'Test Connection'}
            </Button>
            {connectionStatus.marquez === 'success' && (
              <Badge variant="outline" className="text-green-600 dark:text-green-400">
                <Check className="h-3 w-3 mr-1" />
                Connected
              </Badge>
            )}
            {connectionStatus.marquez === 'error' && (
              <Badge variant="outline" className="text-red-600 dark:text-red-400">
                <AlertCircle className="h-3 w-3 mr-1" />
                Failed
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* UI Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>UI Preferences</CardTitle>
          <CardDescription>
            Customize the user interface behavior
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Telemetry Strip</label>
              <p className="text-xs text-muted-foreground mt-1">
                Show system status bar at the top of each page
              </p>
            </div>
            <Button
              variant={settings.telemetryEnabled ? 'default' : 'outline'}
              size="sm"
              onClick={() =>
                setSettings({ ...settings, telemetryEnabled: !settings.telemetryEnabled })
              }
            >
              {settings.telemetryEnabled ? 'Enabled' : 'Disabled'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={handleReset}>
          Reset to Defaults
        </Button>
        <Button onClick={handleSave} className="min-w-[100px]">
          {saved ? (
            <>
              <Check className="mr-2 h-4 w-4" />
              Saved!
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Changes
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
