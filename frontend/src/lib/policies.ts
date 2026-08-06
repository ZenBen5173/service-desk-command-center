import { apiClient } from '@/lib/api-client'

export interface PolicyParameter {
  name: string
  label: string
  type: 'number' | 'boolean' | 'string'
  value: number | boolean | string
  default: number | boolean | string
  min?: number
  max?: number
  step?: number
  help?: string
  /** The Auto workflow input this parameter feeds. */
  maps_to_input?: string
}

export interface Policy {
  id: number
  key: string
  name: string
  description: string | null
  category: string | null
  enabled: boolean
  priority: number
  parameters: PolicyParameter[]
  rule_text: string | null
  applies_to: string[]
  is_builtin: boolean
  updated_at: string | null
  updated_by: string | null
}

export interface PolicyChange {
  id: number
  policy_key: string
  field: string
  old_value: string | null
  new_value: string | null
  changed_by: string | null
  note: string | null
  changed_at: string | null
}

export interface PolicyEvaluation {
  id: number
  policy_key: string | null
  policy_name: string | null
  subject_ref: string | null
  subject_type: string | null
  outcome: string | null
  decision: string | null
  reason: string | null
  threshold_in_force: unknown
  observed_values: unknown
  auto_run_id: string | null
  workflow_name: string | null
  step_name: string | null
  source: string
  evaluated_at: string | null
}

export interface EvaluationSummary {
  total: number
  by_outcome: Record<string, number>
  by_policy: Array<{
    policy_key: string
    policy_name: string | null
    total: number
    outcomes: Record<string, number>
  }>
  last_evaluated_at: string | null
}

export interface EffectiveInputs {
  inputs: Record<string, unknown>
  provenance: Record<string, string>
  policy_count: number
}

export interface PolicyUpdateResult {
  policy: Policy
  changed: string[]
  rejected: Array<{ parameter: string; reason: string }>
}

export const policiesApi = {
  list: () =>
    apiClient.get<{ policies: Policy[]; count: number; active_count: number }>(
      '/api/policies'
    ),
  effectiveInputs: () =>
    apiClient.get<EffectiveInputs>('/api/policies/effective-inputs'),
  changes: (limit = 50) =>
    apiClient.get<{ changes: PolicyChange[]; count: number }>(
      `/api/policies/changes?limit=${limit}`
    ),
  update: (
    key: string,
    payload: {
      parameters?: Record<string, number | boolean | string>
      enabled?: boolean
      note?: string
    }
  ) => apiClient.patch<PolicyUpdateResult>(`/api/policies/${key}`, payload),
  reset: (key: string) =>
    apiClient.post<{ policy: Policy; reset: string[] }>(
      `/api/policies/${key}/reset`
    ),
  evaluations: (limit = 100) =>
    apiClient.get<{
      evaluations: PolicyEvaluation[]
      count: number
      total: number
    }>(`/api/policies/evaluations/log?limit=${limit}`),
  evaluationSummary: () =>
    apiClient.get<EvaluationSummary>('/api/policies/evaluations/summary'),
}

export const OUTCOME_TONE: Record<string, string> = {
  pass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  fail: 'bg-red-50 text-red-600 border-red-200',
  block: 'bg-red-50 text-red-700 border-red-200',
  escalate: 'bg-amber-50 text-amber-700 border-amber-200',
  unknown: 'bg-slate-50 text-slate-600 border-slate-200',
}

export function outcomeTone(outcome: string | null): string {
  return OUTCOME_TONE[outcome || 'unknown'] ?? OUTCOME_TONE.unknown
}
