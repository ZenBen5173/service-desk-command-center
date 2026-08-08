'use client'

import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { agentApi, formatRelative } from '@/lib/agent'
import {
  classificationMeta,
  eliminationApi,
  type EliminationBacklog,
  type EliminationClass,
} from '@/lib/elimination'
import { cn } from '@/lib/utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

function Metric({
  label,
  value,
  hint,
  accent,
  explain,
}: {
  label: string
  value: string
  hint?: string
  accent?: boolean
  /** The long version, on hover. A caveat nobody reads is worse than one they
   *  can reach — but four explanatory cards pushed the ranked list, which is
   *  the point of this page, below the fold. */
  explain?: string
}) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={0.9} />
      <CardContent className='relative z-10 p-5'>
        <div className='flex items-start justify-between gap-2'>
          <p className='text-micro uppercase text-brand-muted'>{label}</p>
          {explain && (
            <Tooltip delayDuration={100}>
              <TooltipTrigger asChild>
                <span
                  tabIndex={0}
                  className='cursor-help text-muted-foreground/70 transition-colors hover:text-brand-navy'
                >
                  <Icons.info className='h-3.5 w-3.5' strokeWidth={1.5} />
                </span>
              </TooltipTrigger>
              <TooltipContent side='top' className='max-w-xs text-xs leading-relaxed'>
                {explain}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
        <p
          className={cn(
            'mt-2 font-display text-[2rem] font-bold leading-none tracking-tight',
            accent ? 'text-gradient' : 'text-brand-navy'
          )}
        >
          {value}
        </p>
        {hint && (
          <p className='mt-2 text-xs text-muted-foreground'>{hint}</p>
        )}
      </CardContent>
    </Card>
  )
}

function ClassRow({ entry, rank }: { entry: EliminationClass; rank: number }) {
  const [open, setOpen] = useState(false)
  const meta = classificationMeta(entry.classification)

  return (
    <div className='rounded-xl border border-border/50 bg-white/70'>
      <button
        onClick={() => setOpen(!open)}
        className='flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-muted/30'
      >
        <span className='mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-navy text-[11px] font-bold text-white'>
          {rank}
        </span>

        <div className='min-w-0 flex-1 space-y-1.5'>
          <div className='flex flex-wrap items-center gap-2'>
            <span className='font-medium text-brand-navy'>{entry.label}</span>
            <span
              className={cn(
                'rounded-full border px-2 py-0.5 text-[11px] font-medium',
                meta.tone
              )}
            >
              {meta.label}
            </span>
            {entry.needs_approval && (
              <span className='rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700'>
                Needs human approval
              </span>
            )}
          </div>

          <div className='flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground'>
            <span>
              <strong className='text-brand-navy'>{entry.volume}</strong> tickets
            </span>
            {entry.breaches !== null && (
              <span>
                <strong className='text-red-600'>{entry.breaches}</strong> breached
              </span>
            )}
            {entry.distinct_reporters !== null && (
              <span>{entry.distinct_reporters} people affected</span>
            )}
            {entry.avg_csat !== null && (
              <span>CSAT {entry.avg_csat.toFixed(1)}</span>
            )}
            {entry.handling_hours !== null && (
              <span>{entry.handling_hours}h handling</span>
            )}
            {entry.languages && entry.languages.length > 1 && (
              <span>{entry.languages.length} languages</span>
            )}
          </div>
        </div>

        <div className='shrink-0 text-right'>
          {entry.deflection_forecast !== null ? (
            <>
              <p className='font-display text-lg font-bold text-emerald-600'>
                {entry.deflection_forecast}
              </p>
              <p className='text-[10px] uppercase text-brand-muted'>
                preventable
              </p>
            </>
          ) : (
            <>
              <p className='font-display text-lg font-bold text-brand-muted'>—</p>
              <p className='text-[10px] uppercase text-brand-muted'>
                no forecast
              </p>
            </>
          )}
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
            <div className='space-y-4 border-t border-border/40 px-4 py-4'>
              <p className='text-xs text-muted-foreground'>{meta.meaning}</p>

              <div>
                <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                  Proposed permanent fix
                </p>
                {entry.proposed_fix ? (
                  <p className='text-sm text-brand-navy'>{entry.proposed_fix}</p>
                ) : (
                  <p className='text-sm text-muted-foreground'>
                    The Operator has not proposed a fix for this class yet.
                  </p>
                )}
                {entry.owning_team && (
                  <p className='mt-1 text-xs text-muted-foreground'>
                    Owning team: {entry.owning_team}
                  </p>
                )}
              </div>

              <div>
                <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                  How this was ranked
                </p>
                <div className='flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground'>
                  <span>Impact score {entry.impact_score}</span>
                  <span>
                    breach rate{' '}
                    {(entry.components.breach_rate * 100).toFixed(0)}%
                  </span>
                  <span>
                    CSAT damage{' '}
                    {(entry.components.csat_damage * 100).toFixed(0)}%
                  </span>
                </div>
                {/* Gaps are stated, never quietly treated as zero. */}
                {entry.missing_inputs.length > 0 && (
                  <p className='mt-1 text-xs text-amber-600'>
                    Not reported by the Operator:{' '}
                    {entry.missing_inputs.join(', ')} — these contributed nothing
                    to the score rather than being assumed.
                  </p>
                )}
              </div>

              {entry.member_keys && entry.member_keys.length > 0 && (
                <div>
                  <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                    Tickets in this class
                    {entry.member_count_shown !== null &&
                      entry.volume > entry.member_count_shown &&
                      ` (showing ${entry.member_count_shown} of ${entry.volume})`}
                  </p>
                  <div className='flex flex-wrap gap-1'>
                    {entry.member_keys.map((key) => (
                      <span
                        key={key}
                        className='rounded border border-border/50 bg-muted/40 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground'
                      >
                        {key}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className='rounded-lg bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground'>
                Reported by{' '}
                <strong className='text-brand-navy'>
                  {entry.source.workflow_name || 'an Operator'}
                </strong>
                {entry.source.step_name && ` · step “${entry.source.step_name}”`}
                {entry.source.run_started_at &&
                  ` · ${formatRelative(entry.source.run_started_at)}`}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function EliminationPage() {
  const [backlog, setBacklog] = useState<EliminationBacklog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    try {
      setBacklog(await eliminationApi.backlog(50))
      setError(null)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not load the backlog.'
      )
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
      await agentApi.sync(40)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const totals = backlog?.totals
  const deflection = backlog?.reported_deflection
  const collapse = deflection?.incident_collapse
  const forecast = deflection?.elimination_forecast
  const consolidation = deflection?.consolidation

  return (
    <TooltipProvider>
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Elimination <span className='text-gradient'>Backlog.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          Closing tickets faster is not the win. These are the classes worth
          making stop existing, ranked by what they cost — found and fixed by
          Operators on Supervity Auto, not by this page.
        </p>
      </motion.div>

      <motion.div
        className='flex flex-wrap items-center gap-3'
        variants={itemVariants}
      >
        <Button onClick={syncThenLoad} disabled={syncing} variant='outline' size='sm'>
          <Icons.activity
            className={cn('mr-2 h-4 w-4', syncing && 'animate-spin')}
            strokeWidth={1.5}
          />
          {syncing ? 'Syncing…' : 'Sync from Auto'}
        </Button>
        {backlog && backlog.generated_from_runs.length > 0 && (
          <span className='text-xs text-muted-foreground'>
            Built from {backlog.generated_from_runs.length} agent run
            {backlog.generated_from_runs.length === 1 ? '' : 's'}
          </span>
        )}
        {error && <span className='text-xs text-red-600'>{error}</span>}
      </motion.div>

      <motion.div
        className='grid grid-cols-2 gap-4 lg:grid-cols-4'
        variants={itemVariants}
      >
        <Metric
          label='Ticket Classes'
          value={loading && !totals ? '…' : String(totals?.classes ?? 0)}
          hint='distinct problems, not tickets'
          explain={
            'Clusters the Operators merged into distinct problems, so one ' +
            'problem is counted once rather than several times under slightly ' +
            'different names.'
          }
        />
        <Metric
          label='Tickets Covered'
          value={
            loading && !totals ? '…' : String(totals?.tickets_in_classes ?? 0)
          }
          hint='inside a classified group'
          explain={
            'Every ticket the Operators placed inside one of these classes. ' +
            'The same problem arrives under many different wordings, which is ' +
            'why the class count is far smaller than the ticket count.'
          }
        />
        <Metric
          label='Collapsed Now'
          value={
            loading && !backlog
              ? '…'
              : collapse
                ? String(collapse.count)
                : String(totals?.deflection_forecast ?? 0)
          }
          hint={
            collapse?.share_pct != null
              ? `${collapse.share_pct}% of tickets — avoided today`
              : 'handling avoided by collapsing incidents'
          }
          accent
          explain={
            'Tickets that shared one root cause and became a single incident ' +
            'with one response. This work is already avoided — it is not a ' +
            'forecast. Never added to the preventable figure beside it.'
          }
        />
        <Metric
          label='Preventable'
          value={
            loading && !backlog
              ? '…'
              : forecast
                ? String(forecast.count)
                : '—'
          }
          hint={
            forecast?.share_pct != null
              ? `${forecast.share_pct}% — forecast, if the fixes ship`
              : 'no forecast reported yet'
          }
          accent
          explain={
            'Tickets in recurring classes that a proposed permanent fix ' +
            'targets. A forecast, and conditional on a human approving the ' +
            'fix. Deliberately kept apart from what has already been avoided.'
          }
        />
      </motion.div>

      {backlog && backlog.warnings.length > 0 && (
        <motion.details
          variants={itemVariants}
          className='rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-2.5'
        >
          {/* Folded, not removed. These are real caveats about how the figures
              were built, but as full-width banners they pushed the ranked list
              — the reason anyone opens this page — below the fold. */}
          <summary className='cursor-pointer text-xs font-medium text-amber-800'>
            {backlog.warnings.length} note
            {backlog.warnings.length === 1 ? '' : 's'} on how these figures were
            built
          </summary>
          <ul className='mt-2 space-y-1.5'>
            {backlog.warnings.map((warning) => (
              <li key={warning} className='text-xs leading-relaxed text-amber-800'>
                {warning}
              </li>
            ))}
          </ul>
        </motion.details>
      )}

      <motion.div variants={itemVariants}>
        <Card className='relative overflow-hidden'>
          <CardWatermark opacity={3} scale={1.1} />
          <CardContent className='relative z-10 p-5'>
            <div className='mb-4'>
              <h2 className='flex items-center gap-2 font-display text-lg font-bold text-brand-navy'>
                <Icons.target
                  className='h-5 w-5 text-brand-cornflower'
                  strokeWidth={1.5}
                />
                Ranked by cost
              </h2>
              <p className='mt-1 text-sm text-muted-foreground'>
                Volume, weighted by SLA breaches and satisfaction damage. Open a
                row to see the proposed fix and how the ranking was reached.
              </p>
            </div>

            {loading && !backlog && (
              <p className='py-8 text-center text-sm text-muted-foreground'>
                Loading backlog…
              </p>
            )}

            {backlog && !backlog.has_data && (
              <div className='rounded-xl border border-dashed border-border/60 py-10 text-center'>
                <p className='text-sm font-medium text-brand-navy'>
                  No ticket classes found yet
                </p>
                <p className='mx-auto mt-2 max-w-md text-xs text-muted-foreground'>
                  This panel fills once the Major-Incident Correlator or the CSAT
                  and Knowledge Loop Operator has run on Supervity Auto. Build
                  them from the specs in{' '}
                  <code className='font-mono'>docs/auto-operators/</code>, run
                  one, then press “Sync from Auto”.
                </p>
              </div>
            )}

            <div className='space-y-2'>
              {backlog?.classes.map((entry, index) => (
                <ClassRow key={entry.key} entry={entry} rank={index + 1} />
              ))}
            </div>

            {backlog && backlog.truncated > 0 && (
              <p className='mt-3 text-xs text-muted-foreground'>
                {backlog.truncated} lower-ranked class
                {backlog.truncated === 1 ? '' : 'es'} not shown.
              </p>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
    </TooltipProvider>
  )
}