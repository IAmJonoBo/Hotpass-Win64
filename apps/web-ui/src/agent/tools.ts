/**
 * Agent Tools - Wrappers for Prefect, Marquez, and Hotpass CLI operations.
 *
 * These helpers are invoked by the assistant to interact with backend services
 * and to trigger long-running CLI jobs through the command runner.
 */

import { prefectApi } from '@/api/prefect'
import { marquezApi } from '@/api/marquez'
import { importsApi } from '@/api/imports'
import { runCommandJob, buildCommandJobLinks, type CommandJobLinks } from '@/api/commands'
import type { CommandJob, ImportTemplatePayload } from '@/types'
import { getCachedToolContract, loadToolContract, type ToolDefinition } from './contract'

export interface ToolResult {
  success: boolean
  data?: unknown
  error?: string
  message: string
}

export interface ToolCall {
  id: string
  tool: string
  timestamp: Date
  result?: ToolResult
}

export interface CommandToolResultData extends CommandJobLinks {
  job: CommandJob
  label?: string
}

const DEFAULT_PROFILE = 'generic'
const DEFAULT_REFINED_PATH = './dist/refined.xlsx'
const PROFILE_SEARCH_PATH = './apps/data-platform/hotpass/profiles'

export const toolContract: ToolDefinition[] = getCachedToolContract()

export async function refreshToolContract(): Promise<ToolDefinition[]> {
  return loadToolContract()
}

/**
 * Shared helper to normalise command job responses for assistant UI.
 */
function formatCommandResult(job: CommandJob, label: string): ToolResult {
  const links = buildCommandJobLinks(job.id)
  return {
    success: true,
    data: {
      job,
      label,
      ...links,
    } satisfies CommandToolResultData,
    message: `${label} dispatched. Job ${job.id} queued.`,
  }
}

async function triggerCommandTool(
  command: string[],
  label: string,
  metadata?: Record<string, unknown>,
  env?: Record<string, string>,
): Promise<ToolResult> {
  try {
    const job = await runCommandJob({
      command,
      label,
      metadata,
      env,
    })
    return formatCommandResult(job, label)
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: `Failed to start "${label}"`,
    }
  }
}

/**
 * List all available Prefect flows.
 */
export async function listFlows(): Promise<ToolResult> {
  try {
    const flows = await prefectApi.getFlows(50)
    return {
      success: true,
      data: flows,
      message: `Found ${flows.length} flows`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: 'Failed to list flows',
    }
  }
}

/**
 * List lineage for a given namespace from Marquez.
 */
export async function listLineage(namespace: string = 'hotpass'): Promise<ToolResult> {
  try {
    const jobs = await marquezApi.getJobs(namespace)
    return {
      success: true,
      data: jobs,
      message: `Found ${jobs.length} jobs in namespace '${namespace}'`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: `Failed to list lineage for namespace '${namespace}'`,
    }
  }
}

/**
 * Navigate to a specific run details page (navigation intent).
 */
export function openRun(runId: string): ToolResult {
  return {
    success: true,
    data: { runId, path: `/runs/${runId}` },
    message: `Navigate to run ${runId}`,
  }
}

/**
 * Get flow runs from Prefect.
 */
export async function getFlowRuns(limit: number = 50): Promise<ToolResult> {
  try {
    const runs = await prefectApi.getFlowRuns({ limit })
    return {
      success: true,
      data: runs,
      message: `Retrieved ${runs.length} flow runs`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: 'Failed to get flow runs',
    }
  }
}

export interface RunRefineOptions {
  profile?: string
  inputDir?: string
  outputPath?: string
  archive?: boolean
}

export async function runRefine(options: RunRefineOptions = {}): Promise<ToolResult> {
  const {
    profile = DEFAULT_PROFILE,
    inputDir = './data',
    outputPath = DEFAULT_REFINED_PATH,
    archive = true,
  } = options

  const command = [
    'uv',
    'run',
    'hotpass',
    'refine',
    '--input-dir',
    inputDir,
    '--output-path',
    outputPath,
    '--profile',
    profile,
  ]
  command.push('--profile-search-path', PROFILE_SEARCH_PATH)
  if (archive) {
    command.push('--archive')
  }

  return triggerCommandTool(command, `Refine (${profile})`, {
    tool: 'runRefine',
    profile,
    inputDir,
    outputPath,
    archive,
  })
}

export async function listImportTemplatesTool(): Promise<ToolResult> {
  try {
    const templates = await importsApi.listTemplates()
    return {
      success: true,
      data: templates,
      message: `Found ${templates.length} import template(s)`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: 'Failed to list import templates',
    }
  }
}

export async function getImportTemplateTool(templateId: string): Promise<ToolResult> {
  if (!templateId) {
    return {
      success: false,
      error: 'Template ID is required',
      message: 'Template ID missing',
    }
  }
  try {
    const template = await importsApi.getTemplate(templateId)
    return {
      success: true,
      data: template,
      message: `Retrieved template "${template.name}"`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: `Failed to fetch template ${templateId}`,
    }
  }
}

export interface SaveImportTemplateOptions {
  id?: string
  name: string
  description?: string
  profile?: string
  tags?: string[]
  payload: ImportTemplatePayload
}

export async function saveImportTemplateTool(options: SaveImportTemplateOptions): Promise<ToolResult> {
  if (!options?.name || !options.payload) {
    return {
      success: false,
      error: 'Template name and payload are required',
      message: 'Invalid template payload',
    }
  }
  try {
    const template = await importsApi.upsertTemplate({
      id: options.id,
      name: options.name,
      description: options.description,
      profile: options.profile,
      tags: options.tags,
      payload: options.payload,
    })
    return {
      success: true,
      data: template,
      message: `Template "${template.name}" saved`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: 'Failed to save template',
    }
  }
}

export async function deleteImportTemplateTool(templateId: string): Promise<ToolResult> {
  if (!templateId) {
    return {
      success: false,
      error: 'Template ID is required',
      message: 'Template ID missing',
    }
  }
  try {
    await importsApi.deleteTemplate(templateId)
    return {
      success: true,
      data: { templateId },
      message: `Template ${templateId} deleted`,
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      message: `Failed to delete template ${templateId}`,
    }
  }
}

export interface RunEnrichOptions {
  profile?: string
  input?: string
  output?: string
  allowNetwork?: boolean
}

export async function runEnrich(options: RunEnrichOptions = {}): Promise<ToolResult> {
  const {
    profile = DEFAULT_PROFILE,
    input = DEFAULT_REFINED_PATH,
    output = './dist/enriched.xlsx',
    allowNetwork = false,
  } = options

  const command = [
    'uv',
    'run',
    'hotpass',
    'enrich',
    '--input',
    input,
    '--output',
    output,
    '--profile',
    profile,
  ]
  command.push('--profile-search-path', PROFILE_SEARCH_PATH)
  if (allowNetwork) {
    command.push('--allow-network', 'true')
  }

  return triggerCommandTool(command, `Enrich (${profile})`, {
    tool: 'runEnrich',
    profile,
    input,
    output,
    allowNetwork,
  })
}

export interface RunQaOptions {
  target?: string
}

export async function runQa(options: RunQaOptions = {}): Promise<ToolResult> {
  const target = options.target ?? 'all'
  const command = [
    'uv',
    'run',
    'hotpass',
    'qa',
    target,
    '--profile-search-path',
    PROFILE_SEARCH_PATH,
  ]

  return triggerCommandTool(command, `QA – ${target}`, {
    tool: 'runQa',
    target,
  })
}

export interface RunPlanResearchOptions {
  dataset?: string
  rowId?: number
  allowNetwork?: boolean
}

export async function runPlanResearch(options: RunPlanResearchOptions = {}): Promise<ToolResult> {
  const {
    dataset = DEFAULT_REFINED_PATH,
    rowId = 0,
    allowNetwork = false,
  } = options

  const command = [
    'uv',
    'run',
    'hotpass',
    'plan',
    'research',
    '--dataset',
    dataset,
    '--row-id',
    rowId.toString(),
  ]
  if (allowNetwork) {
    command.push('--allow-network', 'true')
  }

  return triggerCommandTool(command, 'Plan research', {
    tool: 'runPlanResearch',
    dataset,
    rowId,
    allowNetwork,
  })
}

export interface RunContractsOptions {
  profile?: string
  format?: 'yaml' | 'json'
  output?: string
}

export async function runContracts(options: RunContractsOptions = {}): Promise<ToolResult> {
  const profile = options.profile ?? DEFAULT_PROFILE
  const format = options.format ?? 'yaml'
  const output = options.output ?? `./contracts/${profile}.${format}`

  const command = [
    'uv',
    'run',
    'hotpass',
    'contracts',
    'emit',
    '--profile',
    profile,
    '--format',
    format,
    '--output',
    output,
    '--profile-search-path',
    PROFILE_SEARCH_PATH,
  ]

  return triggerCommandTool(command, `Contracts (${profile})`, {
    tool: 'runContracts',
    profile,
    format,
    output,
  })
}

/**
 * Execute a tool by name with arguments.
 */
export async function executeTool(
  toolName: string,
  args: Record<string, unknown> = {},
): Promise<ToolResult> {
  switch (toolName) {
    case 'listFlows':
      return listFlows()
    case 'listLineage':
      return listLineage(args.namespace as string)
    case 'openRun':
      return openRun(args.runId as string)
    case 'getFlowRuns':
      return getFlowRuns(args.limit as number)
    case 'runRefine':
      return runRefine(args as RunRefineOptions)
    case 'runEnrich':
      return runEnrich(args as RunEnrichOptions)
    case 'runQa':
      return runQa(args as RunQaOptions)
    case 'runPlanResearch':
      return runPlanResearch(args as RunPlanResearchOptions)
    case 'runContracts':
      return runContracts(args as RunContractsOptions)
    default:
      return {
        success: false,
        error: `Unknown tool: ${toolName}`,
        message: 'Tool not found',
      }
  }
}
