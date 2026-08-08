import { apiClient } from '@/lib/api-client'

/** A count the agent reported, with the share of the population it covers. */
export interface CountBlock {
  count: number
  share_pct: number | null
}

/**
 * The figures this project is judged on, exactly as the Operators reported
 * them. A null value means no Operator has produced that metric yet — it is
 * rendered as a dash, never as a zero.
 */
export interface BusinessMetrics {
  csat: {
    average: number
    responses: number | null
    response_rate_pct: number | null
  } | null
  sla: {
    tickets_measured: number
    on_business_hours: number
    elapsed_fallback: number
    /** Share measured on the regional calendar rather than raw elapsed time. */
    authoritative_pct: number
  } | null
  resolution: {
    decisions: number
    allowed: number
    human_review: number
    blocked: number
    auto_resolution_rate_pct: number
    breakdown: Record<string, number>
    /**
     * "orchestrator_cycle" — a whole batch the Orchestrator selected.
     * "individual_operator_runs" — hand-picked tickets tested one at a time.
     * The distinction matters: a rate from three chosen tickets is a weaker
     * claim than one from a batch, and the UI says which it is.
     */
    basis?: 'orchestrator_cycle' | 'individual_operator_runs'
    /** Cleared tickets the resolution Operator actually acted on — an email
     *  sent or a comment posted. Cleared is a decision; this is the deed. */
    acted_on?: number
    cleared_awaiting_action?: number
  } | null
  deflection: {
    collapsed_now: CountBlock | null
    preventable: CountBlock | null
  } | null
  knowledge: {
    articles_drafted: number
    awaiting_approval: number
  } | null
  mttr: number | null
  mttr_note: string
  /** Which workflow produced each metric, so any number can be traced. */
  sources: Record<string, string>
  missing: string[]
  generated_at: string
}

export const businessApi = {
  metrics: () => apiClient.get<BusinessMetrics>('/api/business/metrics'),
}
