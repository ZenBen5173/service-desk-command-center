/**
 * Types and fetchers for live agent activity coming from Supervity Auto.
 *
 * Everything here is read from the backend mirror of Auto, which in turn only
 * ever stores what Auto reported. Nothing on this path invents a number. When
 * there is no data, the UI shows that plainly rather than a placeholder.
 */

import { apiClient } from '@/lib/api-client'

export interface AgentStatus {
  configured: boolean
  base_url: string
  healthy: boolean
  detail: string | null
  mirrored: {
    workflows: number
    orchestrators: number
    operators: number
    runs: number
    activities: number
  }
}

export interface AgentWorkflow {
  id: number
  auto_id: string
  name: string
  description: string | null
  services: string[]
  role: 'orchestrator' | 'operator' | null
  auto_updated_at: string | null
  synced_at: string | null
}

export interface AgentRun {
  id: number
  auto_run_id: string
  auto_workflow_id: string | null
  workflow_name: string | null
  status: string | null
  inputs: unknown
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  timeline_synced: boolean
  timeline_error: string | null
}

export interface AgentActivity {
  id: number
  auto_activity_id: string
  sequence: number | null
  step_id: string | null
  step_name: string | null
  step_description: string | null
  status: string | null
  kind: string | null
  attempt: number | null
  outputs: unknown
  error_details: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
}

export interface WorkflowBreakdown {
  workflow_name: string
  runs: number
  completed: number
  failed: number
}

export interface AgentMetrics {
  has_data: boolean
  total_runs: number
  completed_runs: number
  failed_runs: number
  running_runs: number
  /** Null when nothing has finished yet — render a dash, never a zero. */
  success_rate_pct: number | null
  avg_duration_seconds: number | null
  last_run_at: string | null
  operator_count: number
  orchestrator_count: number
  by_workflow: WorkflowBreakdown[]
}

export interface SyncResult {
  errors: string[]
  workflows: { workflows_seen: number; created: number; updated: number } | null
  runs: { runs_seen: number; created: number; updated: number } | null
  timelines: {
    synced: number
    unavailable_on_auto: number
    still_pending: number
    limit: number
  }
}

export const agentApi = {
  status: () => apiClient.get<AgentStatus>('/api/agent/status'),
  metrics: () => apiClient.get<AgentMetrics>('/api/agent/metrics'),
  workflows: () =>
    apiClient.get<{ workflows: AgentWorkflow[]; count: number }>(
      '/api/agent/workflows'
    ),
  runs: (limit = 50) =>
    apiClient.get<{ runs: AgentRun[]; count: number; total: number }>(
      `/api/agent/runs?limit=${limit}`
    ),
  run: (autoRunId: string, refresh = false) =>
    apiClient.get<{
      run: AgentRun
      activities: AgentActivity[]
      activity_count: number
    }>(`/api/agent/runs/${autoRunId}${refresh ? '?refresh=true' : ''}`),
  sync: (timelineLimit = 25) =>
    apiClient.post<SyncResult>(`/api/agent/sync?timeline_limit=${timelineLimit}`),
}

/** Human-friendly duration. Returns a dash rather than inventing a zero. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const rem = seconds % 60
  if (mins < 60) return rem ? `${mins}m ${rem}s` : `${mins}m`
  const hours = Math.floor(mins / 60)
  return `${hours}h ${mins % 60}m`
}

/** Relative time against the viewer's clock. */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return 'unknown'
  const diff = Date.now() - then
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

export type StatusTone = 'success' | 'danger' | 'active' | 'neutral'

export function statusTone(status: string | null | undefined): StatusTone {
  const s = (status || '').toLowerCase()
  if (s === 'completed' || s === 'success') return 'success'
  if (s === 'failed' || s === 'error') return 'danger'
  if (s === 'running' || s === 'in_progress' || s === 'pending') return 'active'
  return 'neutral'
}
