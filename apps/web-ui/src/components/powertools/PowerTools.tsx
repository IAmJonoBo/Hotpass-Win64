/**
 * Power Tools Launcher
 *
 * Quick access panel for common operations and CLI commands.
 */

import { useState } from 'react'
import { Wrench, Terminal, Play, GitBranch, MessageSquare, Copy, CheckCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface PowerTool {
  id: string
  title: string
  description: string
  command: string
  icon: React.ElementType
  action: () => void
  disabled?: boolean
  disabledReason?: string
}

interface PowerToolsProps {
  onOpenAssistant?: () => void
}

export function PowerTools({ onOpenAssistant }: PowerToolsProps) {
  const navigate = useNavigate()
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null)

  // Check if running in Docker
  const environment =
    import.meta.env.HOTPASS_ENVIRONMENT ||
    import.meta.env.VITE_ENVIRONMENT ||
    'local'
  const isDocker = environment === 'docker'

  const copyCommand = (command: string, id: string) => {
    navigator.clipboard.writeText(command)
    setCopiedCommand(id)
    setTimeout(() => setCopiedCommand(null), 2000)
  }

  const tools: PowerTool[] = [
    {
      id: 'marquez',
      title: 'Start Marquez',
      description: 'Launch Marquez locally for lineage tracking',
      command: 'make marquez-up',
      icon: GitBranch,
      action: () => {
        copyCommand('make marquez-up', 'marquez')
      },
      disabled: isDocker,
      disabledReason: 'Already running in Docker',
    },
    {
      id: 'demo-pipeline',
      title: 'Run Demo Pipeline',
      description: 'Execute a sample refinement pipeline',
      command: 'uv run hotpass refine --input-dir ./data --output-path ./dist/refined.xlsx',
      icon: Play,
      action: () => {
        copyCommand(
          'uv run hotpass refine --input-dir ./data --output-path ./dist/refined.xlsx',
          'demo-pipeline'
        )
      },
    },
    {
      id: 'lineage',
      title: 'Open Lineage',
      description: 'Navigate to the lineage visualization page',
      command: 'Navigate to /lineage',
      icon: GitBranch,
      action: () => {
        navigate('/lineage')
      },
    },
    {
      id: 'assistant',
      title: 'Open Assistant',
      description: 'Launch the AI assistant chat console',
      command: 'Navigate to /assistant',
      icon: MessageSquare,
      action: () => {
        if (onOpenAssistant) {
          onOpenAssistant()
        } else {
          navigate('/assistant')
        }
      },
    },
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Wrench className="h-5 w-5 text-primary" />
          <CardTitle>Power Tools</CardTitle>
        </div>
        <CardDescription>
          Quick actions for common operations
          {isDocker && (
            <Badge variant="outline" className="ml-2 text-xs">
              Docker Mode
            </Badge>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tools.map((tool) => {
            const Icon = tool.icon
            const isCopied = copiedCommand === tool.id

            return (
              <div
                key={tool.id}
                className={cn(
                  'border rounded-lg p-4 space-y-3 transition-colors',
                  tool.disabled
                    ? 'bg-muted/50 border-muted'
                    : 'hover:border-primary hover:bg-accent/50'
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'p-2 rounded-lg',
                        tool.disabled
                          ? 'bg-muted'
                          : 'bg-primary/10 text-primary'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <h3 className="font-medium text-sm">{tool.title}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {tool.description}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Command Display */}
                <div className="relative">
                  <pre
                    className={cn(
                      'bg-muted rounded-md p-2 pr-8 text-xs font-mono flex items-center gap-2 overflow-x-auto',
                      tool.disabled && 'opacity-50'
                    )}
                    tabIndex={0}
                    role="region"
                    aria-label={`Command: ${tool.command}`}
                  >
                    <Terminal className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
                    <code className="flex-1 whitespace-nowrap">{tool.command}</code>
                  </pre>
                  {!tool.disabled && tool.command.startsWith('make') && (
                    <button
                      onClick={() => copyCommand(tool.command, tool.id)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-background rounded"
                      title="Copy command"
                    >
                      {isCopied ? (
                        <CheckCircle className="h-3 w-3 text-green-600 dark:text-green-400" />
                      ) : (
                        <Copy className="h-3 w-3 text-muted-foreground" />
                      )}
                    </button>
                  )}
                </div>

                {/* Action Button */}
                <Button
                  size="sm"
                  className="w-full"
                  onClick={tool.action}
                  disabled={tool.disabled}
                  variant={tool.disabled ? 'outline' : 'default'}
                >
                  {tool.disabled ? (
                    <>
                      <span className="mr-2">⊘</span>
                      {tool.disabledReason}
                    </>
                  ) : tool.command.startsWith('Navigate') ? (
                    <>
                      Go to {tool.title}
                    </>
                  ) : (
                    <>
                      Copy Command
                    </>
                  )}
                </Button>
              </div>
            )
          })}
        </div>

        {/* Docker Notice */}
        {isDocker && (
          <div className="mt-4 bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-sm">
            <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400 font-medium mb-1">
              <Terminal className="h-4 w-4" />
              Running in Docker
            </div>
            <p className="text-xs text-muted-foreground">
              Some commands are unavailable or modified when running in containerized mode.
              Marquez and Prefect are already running as services.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
