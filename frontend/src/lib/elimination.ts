import { apiClient } from '@/lib/api-client'

/** One class of ticket an Operator found worth eliminating. */
export interface EliminationClass {
  key: string
  label: string
  /** MAJOR_INCIDENT, REPEAT_FAILURE, KNOWLEDGE_GAP, etc. Null if unclassified. */
  classification: string | null
  volume: number
  distinct_reporters: number | null
  breaches: number | null
  poor_csat_count: number | null
  avg_csat: number | null
  handling_hours: number | null
  has_kb_article: boolean | null
  proposed_fix: string | null
  owning_team: string | null
  deflection_forecast: number | null
  languages: string[] | null
  member_keys: string[] | null
  member_count_shown: number | null
  needs_approval: boolean
  impact_score: number
  components: {
    volume: number
    breach_rate: number
    csat_damage: number
    handling_hours: number | null
  }
  /** Inputs the Operator did not provide. Shown, not silently defaulted. */
  missing_inputs: string[]
  source: {
    auto_run_id: string
    workflow_name: string | null
    step_name: string | null
    collection: string
    run_started_at: string | null
  }
  raw: unknown
}

/** A count the Operator reported, with the share of the population it covers. */
export interface DeflectionBlock {
  count: number
  share_pct: number | null
}

/**
 * Deflection exactly as the Operator reported it.
 *
 * The two figures are different claims and are never added together:
 * `incident_collapse` is handling effort avoided now by collapsing a burst into
 * one incident; `elimination_forecast` is volume a proposed permanent fix would
 * prevent in future. `total` is the older single-number shape.
 */
export interface ReportedDeflection {
  incident_collapse?: DeflectionBlock | null
  elimination_forecast?: DeflectionBlock | null
  consolidation?: {
    before: number
    after: number
    reduction_pct: number
  } | null
  total?: number
  logic?: string | null
  auto_run_id: string
  workflow_name: string | null
}

export interface EliminationBacklog {
  has_data: boolean
  generated_from_runs: string[]
  superseded_runs?: string[]
  reported_deflection?: ReportedDeflection | null
  totals: {
    classes: number
    tickets_in_classes: number
    deflection_forecast: number
    classes_with_forecast: number
    awaiting_approval: number
    deflection_rate_pct: number | null
  }
  classes: EliminationClass[]
  truncated: number
  warnings: string[]
}

export const eliminationApi = {
  backlog: (limit = 25) =>
    apiClient.get<EliminationBacklog>(`/api/elimination/backlog?limit=${limit}`),
}

/** Presentation metadata per classification. Labels only — no logic. */
export const CLASSIFICATION_META: Record<
  string,
  { label: string; tone: string; meaning: string }
> = {
  MAJOR_INCIDENT: {
    label: 'Systemic',
    tone: 'bg-red-50 text-red-700 border-red-200',
    meaning: 'Many people, one root cause. Fix the cause, not the tickets.',
  },
  REPEAT_FAILURE: {
    label: 'Fix failed',
    tone: 'bg-amber-50 text-amber-700 border-amber-200',
    meaning:
      'One person raising the same problem repeatedly. The earlier fix did not hold.',
  },
  KNOWLEDGE_GAP: {
    label: 'Knowledge gap',
    tone: 'bg-blue-50 text-blue-700 border-blue-200',
    meaning: 'Repeatedly asked, with no article to answer it.',
  },
  ARTICLE_INEFFECTIVE: {
    label: 'Article not working',
    tone: 'bg-purple-50 text-purple-700 border-purple-200',
    meaning: 'An article exists but people still raise tickets.',
  },
  DUPLICATE_BURST: {
    label: 'Duplicates',
    tone: 'bg-slate-50 text-slate-600 border-slate-200',
    meaning: 'Near-identical tickets from one person. Collapse them.',
  },
  FOLLOW_UP_REQUIRED: {
    label: 'Follow-up',
    tone: 'bg-orange-50 text-orange-700 border-orange-200',
    meaning: 'Poor satisfaction scores needing a human reply.',
  },
  BELOW_THRESHOLD: {
    label: 'Below threshold',
    tone: 'bg-slate-50 text-slate-500 border-slate-200',
    meaning: 'Too small to act on yet.',
  },
  HEALTHY: {
    label: 'Healthy',
    tone: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    meaning: 'No action needed.',
  },
}

export function classificationMeta(classification: string | null) {
  if (!classification) {
    return {
      label: 'Unclassified',
      tone: 'bg-slate-50 text-slate-600 border-slate-200',
      meaning: 'The Operator did not classify this class.',
    }
  }
  return (
    CLASSIFICATION_META[classification] ?? {
      label: classification.replace(/_/g, ' ').toLowerCase(),
      tone: 'bg-slate-50 text-slate-600 border-slate-200',
      meaning: 'Classification reported by the Operator.',
    }
  )
}
