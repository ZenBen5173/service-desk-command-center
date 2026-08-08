import { apiClient } from '@/lib/api-client'

export interface WorkbenchException {
  id: number
  dedupe_key: string
  exception_type: string | null
  title: string
  subject_ref: string | null
  subject_type: string | null
  reason: string | null
  agent_recommendation: string | null
  agent_confidence: number | null
  context: Record<string, unknown> | null
  priority: string | null
  auto_run_id: string | null
  workflow_name: string | null
  step_name: string | null
  status: string
  resolution: string | null
  resolution_note: string | null
  resolved_by: string | null
  resolved_at: string | null
  raised_at: string | null
}

export interface WorkbenchSummary {
  total: number
  open: number
  resolved: number
  by_type: Record<string, number>
  by_status: Record<string, number>
  by_resolution: Record<string, number>
  avg_time_to_decision_seconds: number | null
}

export type Resolution = 'approve' | 'reject' | 'modify' | 'more_info'

export const workbenchApi = {
  list: (status?: 'open' | 'resolved', limit = 100) =>
    apiClient.get<{
      exceptions: WorkbenchException[]
      count: number
      total: number
    }>(
      `/api/workbench/exceptions?limit=${limit}${status ? `&status=${status}` : ''}`
    ),
  summary: () => apiClient.get<WorkbenchSummary>('/api/workbench/summary'),
  resolve: (id: number, resolution: Resolution, note?: string) =>
    apiClient.post<WorkbenchException>(
      `/api/workbench/exceptions/${id}/resolve`,
      { resolution, note }
    ),
  reopen: (id: number, note?: string) =>
    apiClient.post<WorkbenchException>(
      `/api/workbench/exceptions/${id}/reopen`,
      { note }
    ),
  ingest: () => apiClient.post<Record<string, unknown>>('/api/workbench/ingest'),

  /** Open items gathered into the classes the Operators put them in. */
  groups: () => apiClient.get<WorkbenchGroupsResponse>('/api/workbench/groups'),

  /** One decision written to every open item in a class. */
  resolveGroup: (groupKey: string, resolution: Resolution, note?: string) =>
    apiClient.post<{
      group_key: string
      resolution: Resolution
      items_decided: number
      tickets: string[]
    }>(`/api/workbench/groups/${encodeURIComponent(groupKey)}/resolve`, {
      resolution,
      note,
    }),
}

/**
 * A class of items the Operators judged to be one problem.
 *
 * The grouping is theirs, not ours — every item carries the cluster the
 * Operator assigned it. Items no Operator clustered are counted separately and
 * stay individual, because they each concern one specific change.
 */
export interface WorkbenchGroup {
  group_key: string
  title: string
  exception_type: string | null
  reason: string | null
  affected_system: string | null
  owning_team: string | null
  proposed_fix: string | null
  kb_status: string | null
  /** The class size the Operator reported, kept apart from how many happen
   *  to be queued here. */
  class_size_reported_by_agent: string | null
  items: number[]
  /** Ticket keys, only where an Operator actually listed them. */
  tickets: string[]
  /** The Operators' own names for this class — the same problem is named
   *  slightly differently on each run, and these are not ticket keys. */
  cluster_names: string[]
  /** False when the Operators counted the class but never named its members. */
  tickets_listed_by_agent: boolean
  item_count: number
  workflow_name: string | null
}

export interface WorkbenchGroupsResponse {
  groups: WorkbenchGroup[]
  group_count: number
  items_in_groups: number
  ungrouped_items: number
  ungrouped_note: string
}

/** Plain-language labels for the exception types Operators raise. */
export const EXCEPTION_META: Record<
  string,
  { label: string; tone: string; meaning: string }
> = {
  change_approval: {
    label: 'Needs approval',
    tone: 'bg-red-50 text-red-700 border-red-200',
    meaning:
      'A change request is awaiting sign-off. The agent will not remediate until a human approves.',
  },
  verification_required: {
    label: 'Verify the fix',
    tone: 'bg-amber-50 text-amber-700 border-amber-200',
    meaning:
      'An earlier change was rolled back. The ticket must be verified before it can close.',
  },
  REPEAT_FAILURE: {
    label: 'Fix never held',
    tone: 'bg-orange-50 text-orange-700 border-orange-200',
    meaning:
      'The same person keeps raising the same problem. Replacing the asset beats fixing it again.',
  },
  human_review: {
    label: 'Human review',
    tone: 'bg-blue-50 text-blue-700 border-blue-200',
    meaning: 'The agent was not confident enough to act alone.',
  },
  exceptions: {
    label: 'Escalated',
    tone: 'bg-slate-50 text-slate-600 border-slate-200',
    meaning: 'The Operator escalated this rather than acting on it.',
  },
}

export function exceptionMeta(type: string | null) {
  if (!type) {
    return {
      label: 'Escalated',
      tone: 'bg-slate-50 text-slate-600 border-slate-200',
      meaning: 'The Operator escalated this rather than acting on it.',
    }
  }
  return (
    EXCEPTION_META[type] ?? {
      label: type.replace(/_/g, ' ').toLowerCase(),
      tone: 'bg-slate-50 text-slate-600 border-slate-200',
      meaning: 'Raised by an Operator on Supervity Auto.',
    }
  )
}

export const RESOLUTION_LABEL: Record<Resolution, string> = {
  approve: 'Approve',
  reject: 'Reject',
  modify: 'Modify',
  more_info: 'Need more info',
}
