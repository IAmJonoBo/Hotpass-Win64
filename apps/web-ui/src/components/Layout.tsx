import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { AssistantDrawer } from './assistant/AssistantDrawer'
import { AgentActivityPanel } from './activity/AgentActivityPanel'
import { TelemetryStrip } from './telemetry/TelemetryStrip'
import { HelpCenter } from './help/HelpCenter'
import { Button } from '@/components/ui/button'
import { HelpCircle } from 'lucide-react'
import { getEnvironmentColor } from '@/lib/utils'
import { FeedbackProvider } from '@/components/feedback/FeedbackProvider'

export function Layout() {
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [assistantMessage, setAssistantMessage] = useState<string>()
  const [activityOpen, setActivityOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  // Get environment from env var or localStorage config
  const environment =
    import.meta.env.HOTPASS_ENVIRONMENT ||
    import.meta.env.VITE_ENVIRONMENT ||
    (typeof window !== 'undefined' && localStorage.getItem('hotpass_environment')) ||
    'local'

  const openAssistant = (message?: string) => {
    setAssistantMessage(message)
    setAssistantOpen(true)
  }

  // Show environment banner for non-local environments
  const showBanner = environment !== 'local'

  return (
    <FeedbackProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar
          environment={environment}
          onOpenAssistant={openAssistant}
          onOpenActivity={() => setActivityOpen(true)}
        />
        <main className="flex-1 overflow-y-auto">
          {showBanner && (
            <div className={`sticky top-0 z-40 px-6 py-2 text-center text-sm font-medium ${getEnvironmentColor(environment)}`}>
              Running in {environment.toUpperCase()} environment
              {environment === 'docker' && ' (containerized)'}
            </div>
          )}
          <TelemetryStrip />
          <div className="container mx-auto p-6 max-w-7xl">
            <Outlet context={{ openAssistant }} />
          </div>
          <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
            <Button
              type="button"
              size="lg"
              className="pointer-events-auto h-12 rounded-full shadow-lg"
              onClick={() => setHelpOpen(true)}
            >
              <HelpCircle className="mr-2 h-5 w-5" />
              Help
            </Button>
          </div>
        </main>
        <AssistantDrawer
          open={assistantOpen}
          onOpenChange={setAssistantOpen}
          initialMessage={assistantMessage}
        />
        <AgentActivityPanel
          open={activityOpen}
          onOpenChange={setActivityOpen}
        />
        <HelpCenter
          open={helpOpen}
          onOpenChange={setHelpOpen}
          onOpenAssistant={openAssistant}
        />
      </div>
    </FeedbackProvider>
  )
}
