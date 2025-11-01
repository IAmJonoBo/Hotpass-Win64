/**
 * Human-in-the-Loop Store
 *
 * Manages HIL approval state and audit history using React Query for persistence.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { HILApproval, HILAuditEntry } from '@/types'
import { readApprovals, readAudit, writeApprovals, writeAudit } from '@/lib/secureStorage'

async function ensureApprovals(): Promise<Record<string, HILApproval>> {
  try {
    return await readApprovals()
  } catch (error) {
    console.error('Failed to load approvals from secure storage', error)
    throw error
  }
}

async function ensureAudit(): Promise<HILAuditEntry[]> {
  try {
    return await readAudit()
  } catch (error) {
    console.error('Failed to load audit history from secure storage', error)
    throw error
  }
}

export function useHILApprovals() {
  return useQuery({
    queryKey: ['hil-approvals'],
    queryFn: ensureApprovals,
  })
}

export function useHILAudit() {
  return useQuery({
    queryKey: ['hil-audit'],
    queryFn: ensureAudit,
  })
}

export function useApproveRun() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      runId,
      operator,
      comment,
    }: {
      runId: string
      operator: string
      comment?: string
    }) => {
      const approvals = await ensureApprovals()
      const audit = await ensureAudit()

      const approval: HILApproval = {
        id: `approval-${Date.now()}`,
        runId,
        status: 'approved',
        operator,
        timestamp: new Date().toISOString(),
        comment,
      }

      const auditEntry: HILAuditEntry = {
        id: `audit-${Date.now()}`,
        runId,
        action: 'approve',
        operator,
        timestamp: new Date().toISOString(),
        comment,
        previousStatus: approvals[runId]?.status,
        newStatus: 'approved',
      }

      approvals[runId] = approval
      await writeApprovals(approvals)
      await writeAudit([auditEntry, ...audit])

      return approval
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hil-approvals'] })
      queryClient.invalidateQueries({ queryKey: ['hil-audit'] })
    },
  })
}

export function useRejectRun() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      runId,
      operator,
      reason,
      comment,
    }: {
      runId: string
      operator: string
      reason?: string
      comment?: string
    }) => {
      const approvals = await ensureApprovals()
      const audit = await ensureAudit()

      const approval: HILApproval = {
        id: `approval-${Date.now()}`,
        runId,
        status: 'rejected',
        operator,
        timestamp: new Date().toISOString(),
        reason,
        comment,
      }

      const auditEntry: HILAuditEntry = {
        id: `audit-${Date.now()}`,
        runId,
        action: 'reject',
        operator,
        timestamp: new Date().toISOString(),
        comment: reason || comment,
        previousStatus: approvals[runId]?.status,
        newStatus: 'rejected',
      }

      approvals[runId] = approval
      await writeApprovals(approvals)
      await writeAudit([auditEntry, ...audit])

      return approval
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hil-approvals'] })
      queryClient.invalidateQueries({ queryKey: ['hil-audit'] })
    },
  })
}

export function useGetRunApproval(runId: string) {
  return useQuery({
    queryKey: ['hil-approval', runId],
    queryFn: async () => {
      const approvals = await ensureApprovals()
      return approvals[runId] || null
    },
  })
}

export function useGetRunHistory(runId: string) {
  return useQuery({
    queryKey: ['hil-history', runId],
    queryFn: async () => {
      const audit = await ensureAudit()
      return audit.filter(entry => entry.runId === runId)
    },
  })
}
