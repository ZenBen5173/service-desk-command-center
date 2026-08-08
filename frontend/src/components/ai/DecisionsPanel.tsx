'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'

import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { formatRelative } from '@/lib/agent'
import { cn } from '@/lib/utils'

/**
 * One ticket's verdict, exactly as the Operator on Auto reported it.
 *
 * Nothing on this page decides anything. The Command Center chooses which
 * ticket to ask about and stores the answer; the ALLOW, the block, the
 * confidence and every policy evaluation are the agent's.
 */
interface Decision {
  issue_key: string
  decision: string
  auto_resolved: boolean
  confidence: number | null
  reason: string | null
  policy_evaluations: Array<Record<string, unknown>>
  /**
   * False when the rule the Operator gave as its reason is not among the gates
   * it logged. Five passing gates and an unexplained block reads as a
   * contradiction; saying which record is missing is better than hiding it or
   * inventing the gate.
   */
  deciding_rule_logged: boolean
  auto_run_id: string
  workflow_name: string | null
  decided_at: string | null
}

interface ResolutionSummary {
  decisions: Decision[]
  tickets_decided: number
  auto_resolved: number
  escalated: number
  auto_resolution_rate_pct: number | null
  avg_confidence: number | null
  /** Verdicts the Operator returned without a score. Blank means it did not
   *  say, not that it was unsure — so these are counted, never zeroed. */
  decisions_without_confidence: number
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

function Metric({
  label,
  value,
  tone,
  hint,
}: {
  label: string
  value: string
  tone?: string
  hint?: string
}) {
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
        {hint && <p className='mt-1.5 text-xs text-muted-foreground'>{hint}</p>}
      </CardContent>
    </Card>
  )
}

function DecisionRow({
  decision,
  onChanged,
}: {
  decision: Decision
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<string | null>(null)
  const allowed = decision.auto_resolved

  // Re-asking about one named ticket, rather than running a sweep and hoping it
  // reaches this one. Showing that a threshold edit changed the agent's mind
  // only works if it is the same ticket before and after.
  const redecide = async () => {
    setBusy(true)
    setOutcome(null)
    try {
      const r = await apiClient.post<{
        before: { decision: string | null }
        after: { decision: string | null; confidence: number | null }
        changed: boolean
        thresholds_in_force: Record<string, unknown>
      }>(`/api/agent/resolution/decide?issue_key=${encodeURIComponent(decision.issue_key)}`, {})
      setOutcome(
        r.changed
          ? `${r.before.decision} → ${r.after.decision} at threshold ${String(
              r.thresholds_in_force.min_auto_confidence
            )}`
          : `Unchanged: ${r.after.decision} at threshold ${String(
              r.thresholds_in_force.min_auto_confidence
            )}`
      )
      onChanged()
    } catch (err) {
      setOutcome(err instanceof Error ? err.message : 'Could not re-decide.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className='relative overflow-hidden'>
      <CardWatermark opacity={3} scale={1} />
      <CardContent className='relative z-10 p-4'>
        <button
          onClick={() => setOpen(!open)}
          className='flex w-full items-start gap-3 text-left'
        >
          <span
            className={cn(
              'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
              allowed ? 'bg-emerald-100' : 'bg-amber-100'
            )}
          >
            {allowed ? (
              <Icons.checkCircle className='h-4 w-4 text-emerald-600' strokeWidth={1.5} />
            ) : (
              <Icons.shield className='h-4 w-4 text-amber-600' strokeWidth={1.5} />
            )}
          </span>

          <div className='min-w-0 flex-1 space-y-1'>
            <div className='flex flex-wrap items-center gap-2'>
              <span className='font-medium text-brand-navy'>{decision.issue_key}</span>
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[11px] font-medium',
                  allowed
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-amber-200 bg-amber-50 text-amber-700'
                )}
              >
                {decision.decision}
              </span>
              <span className='text-[11px] text-muted-foreground'>
                {/* A missing score is shown as such. A dash is honest; a zero
                    would be a claim the Operator never made. */}
                confidence{' '}
                <strong className='text-brand-navy'>
                  {decision.confidence === null ? '—' : decision.confidence.toFixed(2)}
                </strong>
              </span>
            </div>
            <p className='text-sm text-muted-foreground'>{decision.reason}</p>
          </div>

          <Icons.chevronDown
            className={cn(
              'mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>

        {open && (
          <div className='mt-4 space-y-3 border-t border-border/40 pt-4'>
            {!decision.deciding_rule_logged && (
              <div className='rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800'>
                <strong>The rule that decided this is not in the gates below.</strong>{' '}
                The Operator gave its reason as “{decision.reason}” but recorded
                no evaluation for it. Every gate listed here passed — the refusal
                came from a check it applied without logging. Shown rather than
                hidden, and not filled in on the Operator’s behalf.
              </div>
            )}

            {decision.policy_evaluations.length > 0 && (
              <div>
                <p className='mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                  Policy gates
                </p>
                <div className='space-y-1'>
                  {decision.policy_evaluations.map((evaluation, index) => (
                    <div key={index} className='flex flex-wrap items-center gap-2 text-xs'>
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 font-medium',
                          String(evaluation.outcome) === 'pass'
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-red-50 text-red-700'
                        )}
                      >
                        {String(evaluation.outcome)}
                      </span>
                      <span className='text-brand-navy'>
                        {String(evaluation.policy_name ?? evaluation.policy_key)}
                      </span>
                      <span className='text-muted-foreground'>
                        {String(evaluation.reason ?? '')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className='flex flex-wrap items-center gap-3'>
              <Button size='sm' variant='outline' onClick={redecide} disabled={busy}>
                <Icons.repeat
                  className={cn('mr-2 h-3.5 w-3.5', busy && 'animate-spin')}
                />
                {busy ? 'Asking the Operator…' : 'Re-decide this ticket'}
              </Button>
              {outcome && (
                <span className='text-xs font-medium text-brand-navy'>{outcome}</span>
              )}
            </div>

            <p className='rounded-lg bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground'>
              Decided by{' '}
              <strong className='text-brand-navy'>
                {decision.workflow_name ?? 'an Operator'}
              </strong>{' '}
              on Supervity Auto · run{' '}
              <code className='text-[10px]'>{decision.auto_run_id?.slice(0, 8)}</code>
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function DecisionsPanel({ embedded = false }: { embedded?: boolean }) {
  const [data, setData] = useState<ResolutionSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await apiClient.get<ResolutionSummary>('/api/agent/resolution'))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load decisions.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 30000)
    return () => clearInterval(id)
  }, [load])

  const run = async (label: string, path: string) => {
    setBusy(label)
    setMessage(null)
    setError(null)
    try {
      const result = await apiClient.post<Record<string, unknown>>(path, {})
      if (result.ran === false) {
        setMessage(String(result.reason ?? 'Nothing to do.'))
      } else {
        const asked = result.tickets_asked ?? 0
        const resolved = (result.resolution as Record<string, unknown>)?.resolved_now ?? 0
        setMessage(
          `Asked the Operator about ${asked} ticket(s). ${resolved} resolved and notified.`
        )
      }
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : `${label} failed.`)
    } finally {
      setBusy(null)
    }
  }

  const rate = data?.auto_resolution_rate_pct
  const dash = '—'

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {!embedded && (
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Auto <span className='text-gradient'>Resolution.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          Every ticket asked about individually, and answered individually. The
          Operator on Supervity Auto makes each decision; this page records it.
        </p>
        <p className='mt-2 max-w-3xl text-sm text-muted-foreground'>
          The Orchestrator&apos;s sub-workflow calls return nothing, so no
          per-ticket confidence ever reaches its routing step and it escalates
          everything. Asked one ticket at a time, the same Operator answers
          properly — with a real score and a real reason.
        </p>
      </motion.div>
      )}

      <motion.div className='grid grid-cols-2 gap-4 lg:grid-cols-4' variants={itemVariants}>
        <Metric
          label='Tickets decided'
          value={loading && !data ? '…' : String(data?.tickets_decided ?? 0)}
        />
        <Metric
          label='Auto-resolved'
          value={loading && !data ? '…' : String(data?.auto_resolved ?? 0)}
          tone='text-emerald-600'
        />
        <Metric
          label='Escalated'
          value={loading && !data ? '…' : String(data?.escalated ?? 0)}
          tone='text-amber-600'
        />
        <Metric
          label='Auto-resolution rate'
          value={rate === null || rate === undefined ? dash : `${rate}%`}
          hint={
            data?.decisions_without_confidence
              ? `${data.decisions_without_confidence} verdict(s) carry no score`
              : undefined
          }
        />
      </motion.div>

      <motion.div className='flex flex-wrap items-center gap-2' variants={itemVariants}>
        <Button
          onClick={() => run('sweep', '/api/agent/resolution/sweep?limit=20&concurrency=3')}
          disabled={busy !== null}
          size='sm'
        >
          <Icons.zap className={cn('mr-2 h-4 w-4', busy === 'sweep' && 'animate-pulse')} />
          {busy === 'sweep' ? 'Asking the Operator…' : 'Decide new tickets'}
        </Button>

        <Button
          onClick={() =>
            run(
              're-decide',
              '/api/agent/resolution/sweep?limit=20&concurrency=3&redecide=true'
            )
          }
          disabled={busy !== null}
          variant='outline'
          size='sm'
        >
          <Icons.repeat
            className={cn('mr-2 h-4 w-4', busy === 're-decide' && 'animate-spin')}
          />
          {busy === 're-decide' ? 'Re-asking…' : 'Re-decide under current policy'}
        </Button>

        <Button
          onClick={() => run('resolve', '/api/agent/resolution/resolve?limit=25')}
          disabled={busy !== null}
          variant='outline'
          size='sm'
        >
          <Icons.checkCircle
            className={cn('mr-2 h-4 w-4', busy === 'resolve' && 'animate-pulse')}
          />
          {busy === 'resolve' ? 'Resolving…' : 'Resolve everything cleared'}
        </Button>

        {data && (
          <span className='ml-auto text-xs text-muted-foreground'>
            {formatRelative(data.generated_at)}
          </span>
        )}
      </motion.div>

      <motion.p
        variants={itemVariants}
        className='rounded-xl border border-border/60 bg-muted/20 px-4 py-3 text-xs text-muted-foreground'
      >
        <strong className='text-brand-navy'>Re-decide</strong> asks the Operator
        again about tickets it has already ruled on, using the thresholds
        currently set in AI Policies. Change the confidence gate there, press it,
        and the verdicts change — with both the old and the new evaluation kept,
        each naming the threshold that was in force when it was made.
        <br />
        <strong className='text-brand-navy'>Resolve everything cleared</strong>{' '}
        sends real email and comments on real issues. Tickets already acted on
        are skipped, so it is safe to press twice.
      </motion.p>

      {message && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800'
        >
          {message}
        </motion.div>
      )}
      {error && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700'
        >
          {error}
        </motion.div>
      )}

      {!loading && (data?.decisions.length ?? 0) === 0 && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-dashed border-border/60 py-12 text-center'
        >
          <p className='text-sm font-medium text-brand-navy'>No verdicts yet</p>
          <p className='mx-auto mt-2 max-w-md text-xs text-muted-foreground'>
            Press &quot;Decide new tickets&quot; to ask the Operator about the
            tickets the Orchestrator routed. Nothing appears here until an agent
            has actually ruled on one.
          </p>
        </motion.div>
      )}

      <motion.div className='space-y-3' variants={itemVariants}>
        {(data?.decisions ?? []).map((decision) => (
          <DecisionRow key={decision.issue_key} decision={decision} onChanged={load} />
        ))}
      </motion.div>
    </motion.div>
  )
}
