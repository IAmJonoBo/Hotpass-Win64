/**
 * Assistant Chat Console
 *
 * Interactive chat interface for the Hotpass assistant with tool execution and streaming feedback.
 */

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  executeTool,
  toolContract,
  refreshToolContract,
  type ToolResult,
  type ToolCall,
  type CommandToolResultData,
} from '@/agent/tools'
import { useQuery } from '@tanstack/react-query'
import { prefectApi } from '@/api/prefect'
import { useLineageTelemetry } from '@/hooks/useLineageTelemetry'
import { useFeedback } from '@/components/feedback/FeedbackProvider'

const COMMAND_TOOL_NAMES = new Set(['runRefine', 'runEnrich', 'runQa', 'runPlanResearch', 'runContracts'])

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  toolCall?: ToolCall
}

interface AssistantChatProps {
  className?: string
  initialMessage?: string
}

function isCommandToolResultData(data: unknown): data is CommandToolResultData {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Record<string, unknown>
  return (
    typeof candidate.jobId === 'string' &&
    typeof candidate.statusUrl === 'string' &&
    typeof candidate.logUrl === 'string'
  )
}

function extractProfile(text: string): string | undefined {
  const match = text.match(/profile(?:=|\s+)([a-z0-9_-]+)/i)
  return match?.[1]
}

function extractDataset(text: string): string | undefined {
  const match = text.match(/dataset(?:=|\s+)(\S+)/i)
  return match?.[1]
}

function extractRowId(text: string): number | undefined {
  const match = text.match(/row(?:\s+id)?(?:=|#|\s+)(\d+)/i)
  if (!match?.[1]) return undefined
  const parsed = Number.parseInt(match[1], 10)
  return Number.isFinite(parsed) ? parsed : undefined
}

function buildSuggestionList(contract: Array<{ name?: string }>): string[] {
  const base = [
    'run refine profile=aviation',
    'run enrich allow network',
    'run qa target=all',
    'plan research row 5 dataset=./dist/refined.xlsx',
    'run contracts profile=generic',
    'list flows',
    'list lineage namespace=hotpass',
    'open run RUN_ID',
  ]
  const contractNames = contract
    .map(tool => tool.name)
    .filter((name): name is string => typeof name === 'string' && name.length > 0)
  return Array.from(new Set([...base, ...contractNames]))
}

export function AssistantChat({ className, initialMessage }: AssistantChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! I can help you with Hotpass operations. Try asking me to run refine, trigger QA, plan research, or list flows.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState(initialMessage || '')
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastToolCall, setLastToolCall] = useState<ToolCall | null>(null)
  const [contract, setContract] = useState(toolContract)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { addFeedback } = useFeedback()

  // Fetch telemetry data
  const { data: flowRuns = [] } = useQuery({
    queryKey: ['flowRuns'],
    queryFn: async () => {
      try {
        return await prefectApi.getFlowRuns({ limit: 10 })
      } catch {
        return []
      }
    },
    refetchInterval: 15_000,
  })

  const lastPollTime = new Date()
  const environment =
    import.meta.env.HOTPASS_ENVIRONMENT ||
    import.meta.env.VITE_ENVIRONMENT ||
    'local'

  const { data: lineageTelemetry } = useLineageTelemetry()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (initialMessage && messages.length === 1) {
      handleSendMessage(initialMessage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage])

  useEffect(() => {
    refreshToolContract().then(setContract).catch(() => {})
  }, [])

  const handleSendMessage = async (messageText?: string) => {
    const text = messageText ?? input.trim()
    if (!text) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsProcessing(true)

    const lowerText = text.toLowerCase()
    const profile = extractProfile(text)
    const dataset = extractDataset(text)
    const rowId = extractRowId(text)
    const allowNetwork = lowerText.includes('allow network') || lowerText.includes('with network')
    const disableNetwork = lowerText.includes('no network') || lowerText.includes('offline')
    const networkFlag = allowNetwork && !disableNetwork
    const qaTargetMatch = text.match(/run qa\s+([a-z-]+)/i)
    const formatMatch = text.match(/format[:=\s]+([a-z]+)/i)
    const outputMatch = text.match(/output(?:-path)?[:=\s]+(\S+)/i)
    const inputMatch = text.match(/input(?:-dir)?[:=\s]+(\S+)/i)
    const runIdMatch = text.match(/run[:\s]+(\S+)/i)

    let toolName = ''
    const toolArgs: Record<string, unknown> = {}

    if (lowerText.includes('run refine')) {
      toolName = 'runRefine'
      if (profile) toolArgs.profile = profile
      if (inputMatch?.[1]) toolArgs.inputDir = inputMatch[1]
      if (outputMatch?.[1]) toolArgs.outputPath = outputMatch[1]
      if (lowerText.includes('no archive')) toolArgs.archive = false
    } else if (lowerText.includes('run enrich') || lowerText.includes('run enrichment')) {
      toolName = 'runEnrich'
      if (profile) toolArgs.profile = profile
      if (dataset) toolArgs.input = dataset
      if (outputMatch?.[1]) toolArgs.output = outputMatch[1]
      if (networkFlag) toolArgs.allowNetwork = true
    } else if (lowerText.includes('run qa')) {
      toolName = 'runQa'
      if (qaTargetMatch?.[1]) {
        toolArgs.target = qaTargetMatch[1]
      }
    } else if (lowerText.includes('plan research')) {
      toolName = 'runPlanResearch'
      if (dataset) toolArgs.dataset = dataset
      if (typeof rowId === 'number') toolArgs.rowId = rowId
      if (networkFlag) toolArgs.allowNetwork = true
    } else if (lowerText.includes('run contract') || lowerText.includes('run contracts') || lowerText.includes('emit contract')) {
      toolName = 'runContracts'
      if (profile) toolArgs.profile = profile
      if (formatMatch?.[1]) toolArgs.format = formatMatch[1].toLowerCase()
      if (outputMatch?.[1]) toolArgs.output = outputMatch[1]
    } else if (lowerText.includes('list flows') || lowerText.includes('show flows')) {
      toolName = 'listFlows'
    } else if (lowerText.includes('list lineage') || lowerText.includes('show lineage')) {
      toolName = 'listLineage'
      const namespaceMatch = text.match(/namespace[:\s]+([\w-]+)/i)
      if (namespaceMatch?.[1]) {
        toolArgs.namespace = namespaceMatch[1]
      }
    } else if ((lowerText.includes('open run') || lowerText.includes('show run')) && runIdMatch?.[1]) {
      toolName = 'openRun'
      toolArgs.runId = runIdMatch[1]
    } else if (lowerText.includes('get runs') || lowerText.includes('flow runs')) {
      toolName = 'getFlowRuns'
    }

    const isCommandTool = COMMAND_TOOL_NAMES.has(toolName)
    let pendingAssistantId: string | null = null
    let pendingToolCallId: string | null = null

    if (toolName && isCommandTool) {
      pendingAssistantId = `assistant-pending-${Date.now()}`
      pendingToolCallId = `tool-${Date.now()}`
      setMessages(prev => [
        ...prev,
        {
          id: pendingAssistantId!,
          role: 'assistant',
          content: `Running ${toolName}…`,
          timestamp: new Date(),
          toolCall: {
            id: pendingToolCallId!,
            tool: toolName,
            timestamp: new Date(),
          },
        },
      ])
    }

    const updateAssistantMessage = (content: string, toolCall?: ToolCall) => {
      if (pendingAssistantId) {
        setMessages(prev =>
          prev.map(message =>
            message.id === pendingAssistantId
              ? {
                  ...message,
                  content,
                  timestamp: new Date(),
                  toolCall: toolCall ?? message.toolCall,
                }
              : message,
          ),
        )
      } else {
        setMessages(prev => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content,
            timestamp: new Date(),
            toolCall,
          },
        ])
      }
    }

    try {
      let toolResult: ToolResult | null = null
      if (toolName) {
        toolResult = await executeTool(toolName, toolArgs)
      }

      const toolCall: ToolCall | undefined = toolResult
        ? {
            id: pendingToolCallId ?? `tool-${Date.now()}`,
            tool: toolName || 'unknown',
            timestamp: new Date(),
            result: toolResult,
          }
        : undefined

      if (toolCall) {
        setLastToolCall(toolCall)
      }

      let responseContent = ''

      if (toolResult) {
        if (toolResult.success) {
          responseContent = `✓ ${toolResult.message}`

          if (toolName === 'listFlows' && toolResult.data) {
            const flows = toolResult.data as { name: string }[]
            responseContent += `\n\nAvailable flows:\n${flows.map(f => `• ${f.name}`).join('\n')}`
          } else if (toolName === 'listLineage' && toolResult.data) {
            const jobs = toolResult.data as { name: string }[]
            responseContent += `\n\nJobs:\n${jobs.slice(0, 5).map(j => `• ${j.name}`).join('\n')}`
          } else if (toolName === 'openRun' && toolResult.data) {
            const { runId } = toolResult.data as { runId: string }
            responseContent += `\n\nNavigating to run ${runId}...`
          } else if (toolName === 'getFlowRuns' && toolResult.data) {
            const runs = toolResult.data as { name: string; state_name: string }[]
            responseContent += `\n\nRecent runs:\n${runs.slice(0, 5).map(r => `• ${r.name} - ${r.state_name}`).join('\n')}`
          } else if (isCommandTool && toolResult.data && isCommandToolResultData(toolResult.data)) {
            responseContent += `\n\nJob ${toolResult.data.jobId} queued. Use the links below to monitor progress.`
          }
        } else {
          responseContent = `✗ ${toolResult.message}`
          if (toolResult.error) {
            responseContent += `\n\nError: ${toolResult.error}`
          }
          addFeedback({
            variant: 'error',
            title: `${toolName || 'Tool'} failed`,
            description: toolResult.error ?? toolResult.message,
          })
        }
      } else {
        const suggestions = buildSuggestionList(contract)
        responseContent = `I understand you want help, but I didn't recognise a specific command.\nTry:\n${suggestions.map(item => `• ${item}`).join('\n')}`
      }

      updateAssistantMessage(responseContent, toolCall)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error occurred'
      addFeedback({
        variant: 'error',
        title: 'Assistant error',
        description: message,
      })
      updateAssistantMessage(`Error: ${message}`)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          Hotpass Assistant
        </CardTitle>
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-4 space-y-4" style={{ maxHeight: '500px' }}>
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'flex gap-3',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              </div>
            )}
            <div
              className={cn(
                'flex flex-col gap-1 max-w-[80%]',
                message.role === 'user' ? 'items-end' : 'items-start'
              )}
            >
              <div
                className={cn(
                  'rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                )}
              >
                {message.content}
              </div>
              <span className="text-xs text-muted-foreground">
                {formatDistanceToNow(message.timestamp, { addSuffix: true })}
              </span>
              {message.toolCall && (
                <Badge variant="outline" className="text-xs">
                  Tool: {message.toolCall.tool}
                </Badge>
              )}
              {(() => {
                const commandLinks = (() => {
                  const data = message.toolCall?.result?.data
                  return isCommandToolResultData(data) ? data : null
                })()
                if (!commandLinks) return null
                return (
                <div className="mt-2 w-full rounded-lg border border-dashed border-muted-foreground/40 bg-background/80 p-3 text-xs space-y-2">
                  <div className="font-medium">
                        Command job {commandLinks.jobId}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => window.open(commandLinks.statusUrl, '_blank', 'noreferrer')}
                    >
                      View status
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => window.open(commandLinks.logUrl, '_blank', 'noreferrer')}
                    >
                      Stream logs
                    </Button>
                  </div>
                </div>
                )
              })()}
            </div>
            {message.role === 'user' && (
              <div className="flex-shrink-0">
                <div className="h-8 w-8 rounded-full bg-accent flex items-center justify-center">
                  <User className="h-4 w-4" />
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </CardContent>

      <CardFooter className="border-t p-4 flex-col gap-3">
        {/* Tool call indicator */}
        {lastToolCall && (
          <div className="w-full text-xs text-muted-foreground bg-muted rounded-lg p-2">
            <div className="font-medium">Last action:</div>
            <div className="mt-1">
              Tool <code className="bg-background px-1 py-0.5 rounded">{lastToolCall.tool}</code> executed{' '}
              {formatDistanceToNow(lastToolCall.timestamp, { addSuffix: true })}
              {lastToolCall.result && (
                <span className={cn(lastToolCall.result.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400')}>
                  {' '}• {lastToolCall.result.success ? 'Success' : 'Failed'}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Telemetry footer */}
        <div className="w-full text-xs text-muted-foreground border-t pt-2 flex items-center justify-between">
          <span>
            Telemetry: {lineageTelemetry?.incompleteFacets ?? 0} pending backfills ·{' '}
            {flowRuns.length} cached Prefect runs · last sync {formatDistanceToNow(lastPollTime, { addSuffix: true })} · source=marquez
          </span>
          <Badge variant="outline" className="text-xs">Env: {environment}</Badge>
        </div>

        {/* Input */}
        <div className="flex gap-2 w-full">
          <Input
            placeholder="Ask me to run refine, plan research, or list flows..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isProcessing}
            className="flex-1"
          />
          <Button
            onClick={() => handleSendMessage()}
            disabled={isProcessing || !input.trim()}
            size="icon"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </CardFooter>
    </Card>
  )
}
