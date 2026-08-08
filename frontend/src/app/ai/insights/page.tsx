'use client'

import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { agentApi, formatRelative } from '@/lib/agent'
import { cn } from '@/lib/utils'

/**
 * One observation the agents made about the operation.
 *
 * Everything here is assembled from Operator findings. Nothing is inferred by
 * the Command Center — an insights page that invents patterns is worse than an
 * empty one, because it looks equally confident either way.
 */
interface PlanStep {
  seq: number
  action: string
}

/**
 * The improvement plan attached to an insight.
 *
 * `next_action_source` and `owner_source` matter more than they look. An
 * Operator on Auto proposes the permanent fix for some classes and not others;
 * where it did not, the plan falls back to a standard service management
 * playbook. The reader has to be able to tell which sentences are the agent's,
 * so both are labelled in the UI rather than blended into one confident voice.
 */
interface ActionPlan {
  next_action: string
  next_action_source: 'agent' | 'playbook'
  owner: string
  owner_source: 'agent' | 'playbook'
  expected_benefit: string
  benefit_metric: Record<string, unknown>
  steps: PlanStep[]
  effort?: string | null
  horizon?: string | null
}

interface Insight {
  id: string
  type: 'pattern' | 'anomaly' | 'recommendation'
  severity: 'critical' | 'warning' | 'info'
  title: string
  description: string
  data: Record<string, unknown>
  suggested_action: string
  action_type: string
  owning_team?: string | null
  action_plan?: ActionPlan | null
  /** Where the detail lives, when another page owns it. */
  link?: string | null
  link_label?: string | null
  /** Which Operator reported the finding this is built from. */
  source?: string | null
  created_at: string
}

interface InsightsResponse {
  insights: Insight[]
  counts: { total: number; critical: number; warning: number; info: number }
  sources: Record<string, string>
  missing: string[]
  generated_at: string
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.05 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

const SEVERITY_TONE: Record<Insight['severity'], string> = {
  critical: 'bg-red-50 text-red-700 border-red-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
}

const TYPE_META: Record<Insight['type'], { label: string; icon: keyof typeof Icons }> = {
  pattern: { label: 'Pattern', icon: 'activity' },
  anomaly: { label: 'Anomaly', icon: 'alertTriangle' },
  recommendation: { label: 'Recommendation', icon: 'lightbulb' },
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={0.9} />
      <CardContent className='relative z-10 p-5'>
        <p className='text-micro uppercase text-brand-muted'>{label}</p>
        <p
          className={cn(
            'mt-2 font-display text-[2rem] font-bold leading-none',
            tone ?? 'text-brand-navy'
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  )
}

/** Marks whether a line came from an Operator or from the standard playbook. */
function SourceTag({ source }: { source: 'agent' | 'playbook' }) {
  return (
    <span
      className={cn(
        'rounded-full border px-1.5 py-0.5 text-[10px] font-medium',
        source === 'agent'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-border/60 bg-muted/40 text-muted-foreground'
      )}
      title={
        source === 'agent'
          ? 'Proposed by an Operator on Supervity Auto'
          : 'Standard service management playbook — the Operator did not propose one'
      }
    >
      {source === 'agent' ? 'Agent proposed' : 'Playbook'}
    </span>
  )
}

function PlanBlock({ plan }: { plan: ActionPlan }) {
  return (
    <div className='space-y-4'>
      <div className='rounded-lg border border-brand-cornflower/30 bg-brand-cornflower/5 px-3 py-2.5'>
        <div className='mb-1 flex items-center gap-2'>
          <p className='text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
            Next recommended action
          </p>
          <SourceTag source={plan.next_action_source} />
        </div>
        <p className='text-sm font-medium text-brand-navy'>{plan.next_action}</p>
      </div>

      <div className='grid gap-3 sm:grid-cols-3'>
        <div>
          <p className='mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
            Responsible <SourceTag source={plan.owner_source} />
          </p>
          <p className='text-sm text-brand-navy'>{plan.owner}</p>
        </div>
        <div>
          <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
            Effort
          </p>
          <p className='text-sm capitalize text-brand-navy'>{plan.effort ?? '—'}</p>
        </div>
        <div>
          <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
            Timeframe
          </p>
          <p className='text-sm capitalize text-brand-navy'>{plan.horizon ?? '—'}</p>
        </div>
      </div>

      <div>
        <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
          Expected benefit
        </p>
        <p className='text-sm text-brand-navy'>{plan.expected_benefit}</p>
        {Object.keys(plan.benefit_metric ?? {}).length > 0 && (
          <div className='mt-1.5 flex flex-wrap gap-x-4 gap-y-1'>
            {Object.entries(plan.benefit_metric).map(([k, v]) => (
              <span key={k} className='text-xs text-muted-foreground'>
                {k.replace(/_/g, ' ')}:{' '}
                <strong className='text-brand-navy'>{String(v)}</strong>
              </span>
            ))}
          </div>
        )}
      </div>

      {plan.steps.length > 0 && (
        <div>
          <p className='mb-2 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
            Plan
          </p>
          <ol className='space-y-1.5'>
            {plan.steps.map((step) => (
              <li key={step.seq} className='flex gap-2.5 text-sm'>
                <span className='mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-navy/8 text-[11px] font-semibold text-brand-navy'>
                  {step.seq}
                </span>
                <span className='text-brand-navy'>{step.action}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

function InsightRow({ insight }: { insight: Insight }) {
  const [open, setOpen] = useState(false)
  const meta = TYPE_META[insight.type]
  const Icon = Icons[meta.icon] as React.ElementType

  return (
    <Card className='relative overflow-hidden'>
      <CardWatermark opacity={3} scale={1} />
      <CardContent className='relative z-10 p-4'>
        <button
          onClick={() => setOpen(!open)}
          className='flex w-full items-start gap-3 text-left'
        >
          <Icon
            className='mt-0.5 h-5 w-5 shrink-0 text-brand-cornflower'
            strokeWidth={1.5}
          />

          <div className='min-w-0 flex-1 space-y-1.5'>
            <div className='flex flex-wrap items-center gap-2'>
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize',
                  SEVERITY_TONE[insight.severity]
                )}
              >
                {insight.severity}
              </span>
              <span className='rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground'>
                {meta.label}
              </span>
              {insight.owning_team && (
                <span className='text-[11px] text-muted-foreground'>
                  {insight.owning_team}
                </span>
              )}
            </div>

            <p className='font-medium text-brand-navy'>{insight.title}</p>
            <p className='text-sm text-muted-foreground'>{insight.description}</p>
          </div>

          <Icons.chevronDown
            className={cn(
              'mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className='overflow-hidden'
            >
              <div className='mt-4 space-y-4 border-t border-border/40 pt-4'>
                {insight.action_plan ? (
                  <PlanBlock plan={insight.action_plan} />
                ) : (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      What to do
                    </p>
                    <p className='text-sm text-brand-navy'>
                      {insight.suggested_action}
                    </p>
                  </div>
                )}

                <div>
                  <p className='mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                    Evidence
                  </p>
                  <div className='flex flex-wrap gap-x-4 gap-y-1'>
                    {Object.entries(insight.data)
                      .filter(([, v]) => v !== null && v !== undefined)
                      .map(([k, v]) => (
                        <span key={k} className='text-xs text-muted-foreground'>
                          {k.replace(/_/g, ' ')}:{' '}
                          <strong className='text-brand-navy'>
                            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                          </strong>
                        </span>
                      ))}
                  </div>
                </div>

                {insight.link && (
                  <a
                    href={insight.link}
                    className='inline-flex items-center gap-1.5 text-sm font-medium text-brand-cornflower hover:underline'
                  >
                    {insight.link_label ?? 'Open'} →
                  </a>
                )}

                {insight.source && (
                  <p className='rounded-lg bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground'>
                    Observed by{' '}
                    <strong className='text-brand-navy'>{insight.source}</strong>{' '}
                    on Supervity Auto
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

export default function InsightsPage() {
  const [data, setData] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [filter, setFilter] = useState<'all' | Insight['type']>('all')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await apiClient.get<InsightsResponse>('/api/insights'))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load insights.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 30000)
    return () => clearInterval(id)
  }, [load])

  const syncThenLoad = async () => {
    setSyncing(true)
    try {
      await agentApi.sync(60)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const shown =
    filter === 'all'
      ? (data?.insights ?? [])
      : (data?.insights ?? []).filter((i) => i.type === filter)

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          AI <span className='text-gradient'>Insights.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          What the operation looks like from above — recurring problems, incidents
          forming, knowledge gaps, breach forecasts and where the load falls.
        </p>
        <p className='mt-2 max-w-3xl text-sm text-muted-foreground'>
          Every insight is built from something an Operator actually observed on
          Supervity Auto. Open one to see the evidence and which agent found it.
        </p>
      </motion.div>

      <motion.div
        className='grid grid-cols-2 gap-4 lg:grid-cols-4'
        variants={itemVariants}
      >
        <Metric
          label='Insights'
          value={loading && !data ? '…' : String(data?.counts.total ?? 0)}
        />
        <Metric
          label='Critical'
          value={loading && !data ? '…' : String(data?.counts.critical ?? 0)}
          tone='text-red-600'
        />
        <Metric
          label='Warning'
          value={loading && !data ? '…' : String(data?.counts.warning ?? 0)}
          tone='text-amber-600'
        />
        <Metric
          label='Info'
          value={loading && !data ? '…' : String(data?.counts.info ?? 0)}
          tone='text-blue-600'
        />
      </motion.div>

      <motion.div
        className='flex flex-wrap items-center gap-2'
        variants={itemVariants}
      >
        {(['all', 'anomaly', 'pattern', 'recommendation'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              'rounded-full border px-3 py-1.5 text-sm font-medium capitalize transition-colors',
              filter === f
                ? 'border-brand-navy bg-brand-navy text-white'
                : 'border-border/60 bg-white/60 text-muted-foreground hover:text-brand-navy'
            )}
          >
            {f === 'all' ? 'All' : f === 'anomaly' ? 'Anomalies' : `${f}s`}
          </button>
        ))}
        <Button
          onClick={syncThenLoad}
          disabled={syncing}
          variant='outline'
          size='sm'
          className='ml-auto'
        >
          <Icons.activity
            className={cn('mr-2 h-4 w-4', syncing && 'animate-spin')}
            strokeWidth={1.5}
          />
          {syncing ? 'Syncing…' : 'Sync from Auto'}
        </Button>
        {data && (
          <span className='text-xs text-muted-foreground'>
            {formatRelative(data.generated_at)}
          </span>
        )}
        {error && <span className='text-xs text-red-600'>{error}</span>}
      </motion.div>

      {data?.missing.map((m) => (
        <motion.div
          key={m}
          variants={itemVariants}
          className='rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800'
        >
          {m}
        </motion.div>
      ))}

      {!loading && shown.length === 0 && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-dashed border-border/60 py-12 text-center'
        >
          <p className='text-sm font-medium text-brand-navy'>
            Nothing to report
          </p>
          <p className='mx-auto mt-2 max-w-md text-xs text-muted-foreground'>
            Insights appear once an Operator has run and reported findings.
            Nothing here is generated without an agent observing it first.
          </p>
        </motion.div>
      )}

      <motion.div className='space-y-3' variants={itemVariants}>
        {shown.map((insight) => (
          <InsightRow key={insight.id} insight={insight} />
        ))}
      </motion.div>
    </motion.div>
  )
}
