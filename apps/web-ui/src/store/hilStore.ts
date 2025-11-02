/**
 * Human-in-the-Loop Store
 *
 * Manages HIL approval state and audit history using React Query for persistence.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { HILApproval, HILAuditEntry } from '@/types'
import { readApprovals, readAudit, writeApprovals, writeAudit } from '@/lib/secureStorage'
import { fetchHilApprovals, fetchHilAudit, submitHilApproval } from '@/api/hil'

async function ensureApprovals(): Promise<Record<string, HILApproval>> {
  try {
    const approvals = await fetchHilApprovals()
    try {
      await writeApprovals(approvals)
    } catch {
      // ignore secure storage errors (likely disabled)
    }
    return approvals
  } catch (error) {
    console.warn('Failed to fetch approvals from server, falling back to secure storage', error)
    return readApprovals()
  }
}

async function ensureAudit(limit?: number): Promise<HILAuditEntry[]> {
  try {
    const entries = await fetchHilAudit(limit)
    try {
      await writeAudit(entries)
    } catch {
      // ignore secure storage errors
    }
    return entries
  } catch (error) {
    console.warn('Failed to fetch audit history from server, falling back to secure storage', error)
    return readAudit()
  }
}

export function useHILApprovals() {
  return useQuery({
    queryKey: ['hil', 'approvals'],
    queryFn: ensureApprovals,
    staleTime: 30_000,
  })
}

export function useHILAudit(limit = 100) {
  return useQuery({
    queryKey: ['hil', 'audit', limit],
    queryFn: () => ensureAudit(limit),
    staleTime: 30_000,
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
      return submitHilApproval({
        runId,
        status: 'approved',
        operator,
        comment,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hil'] })
      queryClient.invalidateQueries({ queryKey: ['activity'] })
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
      return submitHilApproval({
        runId,
        status: 'rejected',
        operator,
        reason,
        comment,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hil'] })
      queryClient.invalidateQueries({ queryKey: ['activity'] })
    },
  })
}

export function useGetRunApproval(runId: string) {
  return useQuery({
    queryKey: ['hil', 'approval', runId],
    queryFn: async () => {
      const approvals = await ensureApprovals()
      return approvals[runId] || null
    },
  })
}

export function useGetRunHistory(runId: string) {
  return useQuery({
    queryKey: ['hil', 'history', runId],
    queryFn: async () => {
      const audit = await ensureAudit(200)
      return audit.filter(entry => entry.runId === runId)
    },
  })
}
