'use client'

import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import {
  agentApi,
  formatDuration,
  formatRelative,
  statusTone,
  type AgentActivity,
  type AgentRun,
} from '@/lib/agent'
import { cn } from '@/lib/utils'

const TONE_CLASSES: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  danger: 'bg-red-50 text-red-600 border-red-200',
  active: 'bg-blue-50 text-blue-600 border-blue-200',
  neutral: 'bg-slate-50 text-slate-600 border-slate-200',
}

function StatusPill({ status }: { status: string | null }) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize',
        TONE_CLASSES[statusTone(status)]
      )}
    >
      {status || 'unknown'}
    </span>
  )
}

/**
 * The activity timeline for one run.
 *
 * This renders Auto's step outputs verbatim. Round 1 showed Auto's chat-style
 * summaries contradicting its own timeline — inventing ticket numbers,
 * identities and confidence values. So the authoritative JSON is what gets
 * shown here, and it is what should be believed.
 */
function RunTimeline({ autoRunId }: { autoRunId: string }) {
  const [activities, setActivities] = useState<AgentActivity[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openStep, setOpenStep] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void agentApi
      .run(autoRunId)
      .then((data) => {
        if (!cancelled) setActivities(data.activities)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : 'Could not load timeline'
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [autoRunId])

  if (loading) {
    return (
      <p className='px-4 py-3 text-xs text-muted-foreground'>
        Loading activity timeline…
      </p>
    )
  }

  if (error) {
    return <p className='px-4 py-3 text-xs text-red-600'>{error}</p>
  }

  if (!activities || activities.length === 0) {
    return (
      <p className='px-4 py-3 text-xs text-muted-foreground'>
        Auto did not return a step timeline for this run. Older runs are listed
        but their timelines are no longer served.
      </p>
    )
  }

  return (
    <div className='space-y-1 border-t border-border/40 bg-muted/20 px-4 py-3'>
      {activities.map((activity) => {
        const isOpen = openStep === activity.id
        return (
          <div key={activity.id} className='rounded-lg bg-white/70'>
            <button
              onClick={() => setOpenStep(isOpen ? null : activity.id)}
              className='flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-white'
            >
              <span className='w-5 shrink-0 text-center font-mono text-[11px] text-muted-foreground'>
                {(activity.sequence ?? 0) + 1}
              </span>
              <span className='min-w-0 flex-1 truncate text-xs font-medium text-brand-navy'>
                {activity.step_name || activity.step_id || 'Unnamed step'}
              </span>
              {activity.attempt && activity.attempt > 1 && (
                <span className='shrink-0 text-[11px] text-amber-600'>
                  attempt {activity.attempt}
                </span>
              )}
              <span className='shrink-0 text-[11px] text-muted-foreground'>
                {formatDuration(activity.duration_seconds)}
              </span>
              <StatusPill status={activity.status} />
              <Icons.chevronDown
                className={cn(
                  'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
                  isOpen && 'rotate-180'
                )}
              />
            </button>

            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className='overflow-hidden'
                >
                  <div className='space-y-2 px-3 pb-3'>
                    {activity.step_description && (
                      <p className='text-[11px] text-muted-foreground'>
                        {activity.step_description}
                      </p>
                    )}
                    {activity.error_details && (
                      <pre className='overflow-x-auto rounded-lg bg-red-50 p-2 font-mono text-[11px] text-red-700'>
                        {activity.error_details}
                      </pre>
                    )}
                    <div>
                      <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                        Authoritative output from Auto
                      </p>
                      <pre className='max-h-64 overflow-auto rounded-lg border border-border/40 bg-slate-50 p-2 font-mono text-[11px] leading-relaxed text-slate-700'>
                        {JSON.stringify(activity.outputs ?? {}, null, 2)}
                      </pre>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}

interface AgentRunsPanelProps {
  runs: AgentRun[]
  loading: boolean
  className?: string
}

export function AgentRunsPanel({ runs, loading, className }: AgentRunsPanelProps) {
  const [openRun, setOpenRun] = useState<string | null>(null)

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardWatermark opacity={3} scale={1.1} />
      <CardHeader className='relative z-10 pb-3'>
        <CardTitle className='flex items-center gap-2'>
          <Icons.activity
            className='h-5 w-5 text-brand-cornflower'
            strokeWidth={1.5}
          />
          Agent Activity
        </CardTitle>
        <p className='mt-1 text-sm text-muted-foreground'>
          Every run below happened on Supervity Auto. Open one to see the
          step-by-step record.
        </p>
      </CardHeader>

      <CardContent className='relative z-10 pt-0'>
        {loading && runs.length === 0 && (
          <p className='py-6 text-center text-sm text-muted-foreground'>
            Loading agent runs…
          </p>
        )}

        {!loading && runs.length === 0 && (
          <div className='rounded-xl border border-dashed border-border/60 py-8 text-center'>
            <p className='text-sm font-medium text-brand-navy'>
              No agent runs mirrored yet
            </p>
            <p className='mt-1 text-xs text-muted-foreground'>
              Press “Sync from Auto” above, or trigger a run on
              auto.supervity.ai.
            </p>
          </div>
        )}

        <div className='divide-y divide-border/40'>
          {runs.map((run) => {
            const isOpen = openRun === run.auto_run_id
            return (
              <div key={run.auto_run_id}>
                <button
                  onClick={() => setOpenRun(isOpen ? null : run.auto_run_id)}
                  className='flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-muted/30'
                >
                  <Icons.chevronDown
                    className={cn(
                      'h-4 w-4 shrink-0 text-muted-foreground transition-transform',
                      isOpen && 'rotate-180'
                    )}
                  />
                  <span className='min-w-0 flex-1 truncate text-sm font-medium text-brand-navy'>
                    {run.workflow_name || 'Unnamed workflow'}
                  </span>
                  <span className='hidden shrink-0 text-xs text-muted-foreground sm:inline'>
                    {formatDuration(run.duration_seconds)}
                  </span>
                  <span className='hidden shrink-0 text-xs text-muted-foreground md:inline'>
                    {formatRelative(run.started_at)}
                  </span>
                  <StatusPill status={run.status} />
                </button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className='overflow-hidden'
                    >
                      <div className='pb-3'>
                        <RunTimeline autoRunId={run.auto_run_id} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
