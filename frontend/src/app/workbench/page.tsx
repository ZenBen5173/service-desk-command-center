'use client'

import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { agentApi, formatRelative } from '@/lib/agent'
import {
  exceptionMeta,
  workbenchApi,
  RESOLUTION_LABEL,
  type Resolution,
  type WorkbenchException,
  type WorkbenchGroup,
  type WorkbenchGroupsResponse,
  type WorkbenchSummary,
} from '@/lib/workbench'
import { cn } from '@/lib/utils'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

const RESOLUTIONS: Resolution[] = ['approve', 'reject', 'modify', 'more_info']

/**
 * One class of items, decided once.
 *
 * A queue of hundreds is not hundreds of decisions — most of it is the same
 * problem arriving under different ticket numbers, and the Operators already
 * said which items belong together. Deciding a class writes the same decision
 * to every open item in it, individually, so the audit trail keeps a row per
 * item rather than one row standing in for many.
 */
function GroupCard({
  group,
  onChanged,
}: {
  group: WorkbenchGroup
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState<Resolution | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!choice) return
    if (choice === 'modify' && !note.trim()) {
      setError('A note is required when modifying the agent’s recommendation.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await workbenchApi.resolveGroup(group.group_key, choice, note.trim() || undefined)
      setChoice(null)
      setNote('')
      setOpen(false)
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record the decision.')
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
          <span className='mt-0.5 flex h-9 min-w-9 shrink-0 items-center justify-center rounded-lg bg-brand-navy/8 px-2 font-display text-sm font-bold text-brand-navy'>
            {group.item_count}
          </span>

          <div className='min-w-0 flex-1 space-y-1'>
            <div className='flex flex-wrap items-center gap-2'>
              <span className='font-medium capitalize text-brand-navy'>
                {group.group_key}
              </span>
              {group.owning_team && (
                <span className='rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground'>
                  {group.owning_team}
                </span>
              )}
              {group.kb_status && (
                <span className='rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700'>
                  KB {group.kb_status}
                </span>
              )}
            </div>
            <p className='text-sm text-muted-foreground'>{group.title}</p>
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
                {group.proposed_fix && (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      The agent’s proposed permanent fix
                    </p>
                    <p className='text-sm text-brand-navy'>{group.proposed_fix}</p>
                  </div>
                )}

                <div className='flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground'>
                  <span>
                    items here:{' '}
                    <strong className='text-brand-navy'>{group.item_count}</strong>
                  </span>
                  {group.class_size_reported_by_agent && (
                    <span>
                      class size reported by the agent:{' '}
                      <strong className='text-brand-navy'>
                        {group.class_size_reported_by_agent}
                      </strong>
                    </span>
                  )}
                  {group.affected_system && (
                    <span>
                      system:{' '}
                      <strong className='text-brand-navy'>
                        {group.affected_system}
                      </strong>
                    </span>
                  )}
                </div>

                {group.tickets.length > 0 ? (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      Tickets covered
                    </p>
                    <p className='text-xs text-muted-foreground'>
                      {group.tickets.join(' · ')}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      Tickets covered
                    </p>
                    {/* The Operators size these classes without naming their
                        members. Saying so beats listing the nearest available
                        strings and letting them read as ticket keys. */}
                    <p className='text-xs text-muted-foreground'>
                      Not listed. The Operator reported a class of{' '}
                      <strong className='text-brand-navy'>
                        {group.class_size_reported_by_agent ?? 'unknown'}
                      </strong>{' '}
                      tickets but did not name them, so this decision applies to
                      the{' '}
                      <strong className='text-brand-navy'>
                        {group.item_count}
                      </strong>{' '}
                      queue items below, not to individual tickets.
                    </p>
                  </div>
                )}

                {group.cluster_names.length > 0 && (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      Merged from these Operator clusters
                    </p>
                    <p className='text-xs text-muted-foreground'>
                      {group.cluster_names.join(' · ')}
                    </p>
                  </div>
                )}

                <div className='flex flex-wrap gap-2'>
                  {RESOLUTIONS.map((r) => (
                    <button
                      key={r}
                      onClick={() => setChoice(r)}
                      className={cn(
                        'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                        choice === r
                          ? 'border-brand-navy bg-brand-navy text-white'
                          : 'border-border/60 bg-white/60 text-muted-foreground hover:text-brand-navy'
                      )}
                    >
                      {RESOLUTION_LABEL[r]}
                    </button>
                  ))}
                </div>

                {choice && (
                  <div className='space-y-2'>
                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      rows={2}
                      placeholder={
                        choice === 'modify'
                          ? 'What should happen instead? (required)'
                          : 'Why (optional, but it goes on the record)'
                      }
                      className='w-full rounded-lg border border-border/60 bg-white/70 px-3 py-2 text-sm'
                    />
                    <div className='flex items-center gap-2'>
                      <Button size='sm' onClick={submit} disabled={busy}>
                        {busy
                          ? 'Recording…'
                          : `Apply to all ${group.item_count} items`}
                      </Button>
                      <span className='text-[11px] text-muted-foreground'>
                        Written to each item separately, noting it was decided as
                        a class.
                      </span>
                    </div>
                    {error && <p className='text-xs text-red-600'>{error}</p>}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint?: string
}) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={0.9} />
      <CardContent className='relative z-10 p-5'>
        <p className='text-micro uppercase text-brand-muted'>{label}</p>
        <p className='mt-2 font-display text-[2rem] font-bold leading-none text-brand-navy'>
          {value}
        </p>
        {hint && <p className='mt-2 text-xs text-muted-foreground'>{hint}</p>}
      </CardContent>
    </Card>
  )
}

/** Renders whatever context the Operator attached, without assuming its shape. */
function ContextTable({ context }: { context: Record<string, unknown> | null }) {
  if (!context || Object.keys(context).length === 0) {
    return (
      <p className='text-xs text-muted-foreground'>
        The Operator attached no additional context to this item.
      </p>
    )
  }

  return (
    <div className='space-y-1'>
      {Object.entries(context).map(([key, value]) => {
        const isUrl = typeof value === 'string' && value.startsWith('http')
        const display =
          typeof value === 'object' && value !== null
            ? JSON.stringify(value)
            : String(value)
        return (
          <div key={key} className='flex gap-2 text-xs'>
            <span className='w-40 shrink-0 text-muted-foreground'>
              {key.replace(/_/g, ' ')}
            </span>
            {isUrl ? (
              <a
                href={value as string}
                target='_blank'
                rel='noreferrer'
                className='min-w-0 flex-1 truncate text-brand-cornflower underline'
              >
                {display}
              </a>
            ) : (
              <span className='min-w-0 flex-1 break-words text-brand-navy'>
                {display}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ExceptionCard({
  item,
  onChanged,
}: {
  item: WorkbenchException
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState<Resolution | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const meta = exceptionMeta(item.exception_type)
  const isOpen = item.status === 'open'

  const submit = async () => {
    if (!choice) return
    setBusy(true)
    setError(null)
    try {
      await workbenchApi.resolve(item.id, choice, note || undefined)
      setChoice(null)
      setNote('')
      onChanged()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not record the decision.'
      )
    } finally {
      setBusy(false)
    }
  }

  const reopen = async () => {
    setBusy(true)
    try {
      await workbenchApi.reopen(item.id)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className={cn('relative overflow-hidden', !isOpen && 'opacity-75')}>
      <CardWatermark opacity={3} scale={1} />
      <CardContent className='relative z-10 p-4'>
        <button
          onClick={() => setOpen(!open)}
          className='flex w-full items-start gap-3 text-left'
        >
          <div className='min-w-0 flex-1 space-y-1.5'>
            <div className='flex flex-wrap items-center gap-2'>
              {item.subject_ref && (
                <span className='font-mono text-sm font-semibold text-brand-navy'>
                  {item.subject_ref}
                </span>
              )}
              <span
                className={cn(
                  'rounded-full border px-2 py-0.5 text-[11px] font-medium',
                  meta.tone
                )}
              >
                {meta.label}
              </span>
              {!isOpen && (
                <span className='rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700'>
                  {item.resolution
                    ? (RESOLUTION_LABEL[item.resolution as Resolution] ??
                      item.resolution)
                    : 'Resolved'}
                </span>
              )}
            </div>

            <p className='text-sm text-brand-navy'>{item.title}</p>

            <div className='flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground'>
              {item.workflow_name && <span>{item.workflow_name}</span>}
              <span>raised {formatRelative(item.raised_at)}</span>
              {item.agent_confidence !== null && (
                <span>agent confidence {item.agent_confidence}</span>
              )}
            </div>
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
                <p className='text-xs text-muted-foreground'>{meta.meaning}</p>

                {item.reason && (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      Why the agent stopped
                    </p>
                    <p className='text-sm text-brand-navy'>{item.reason}</p>
                  </div>
                )}

                {item.agent_recommendation && (
                  <div>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      What the agent would have done
                    </p>
                    <p className='text-sm text-brand-navy'>
                      {item.agent_recommendation}
                    </p>
                  </div>
                )}

                <div>
                  <p className='mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                    Context from the Operator
                  </p>
                  <ContextTable context={item.context} />
                </div>

                {isOpen ? (
                  <div className='space-y-2 rounded-lg border border-border/50 bg-muted/20 p-3'>
                    <p className='text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      Your decision
                    </p>
                    <div className='flex flex-wrap gap-2'>
                      {RESOLUTIONS.map((r) => (
                        <button
                          key={r}
                          onClick={() => setChoice(r)}
                          className={cn(
                            'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                            choice === r
                              ? 'border-brand-navy bg-brand-navy text-white'
                              : 'border-border/60 bg-white text-muted-foreground hover:text-brand-navy'
                          )}
                        >
                          {RESOLUTION_LABEL[r]}
                        </button>
                      ))}
                    </div>

                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder={
                        choice === 'modify'
                          ? 'Required — what are you changing, and why?'
                          : 'Optional note explaining your decision'
                      }
                      rows={2}
                      className='w-full rounded-lg border border-border/60 bg-white p-2 text-xs text-brand-navy outline-none focus:border-brand-cornflower'
                    />

                    {error && <p className='text-xs text-red-600'>{error}</p>}

                    <Button
                      onClick={submit}
                      disabled={!choice || busy}
                      variant='gradient'
                      size='sm'
                    >
                      {busy ? 'Recording…' : 'Record decision'}
                    </Button>
                  </div>
                ) : (
                  <div className='rounded-lg border border-border/50 bg-muted/20 p-3'>
                    <p className='text-xs text-brand-navy'>
                      {item.resolution
                        ? (RESOLUTION_LABEL[item.resolution as Resolution] ??
                          item.resolution)
                        : 'Resolved'}{' '}
                      by {item.resolved_by} {formatRelative(item.resolved_at)}
                    </p>
                    {item.resolution_note && (
                      <p className='mt-1 text-xs text-muted-foreground'>
                        “{item.resolution_note}”
                      </p>
                    )}
                    <Button
                      onClick={reopen}
                      disabled={busy}
                      variant='outline'
                      size='sm'
                      className='mt-2'
                    >
                      Reopen
                    </Button>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

export default function WorkbenchPage() {
  const [items, setItems] = useState<WorkbenchException[]>([])
  const [summary, setSummary] = useState<WorkbenchSummary | null>(null)
  const [groups, setGroups] = useState<WorkbenchGroupsResponse | null>(null)
  const [filter, setFilter] = useState<'open' | 'resolved' | 'all' | 'classes'>(
    'open'
  )
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const listStatus =
        filter === 'all' || filter === 'classes' ? undefined : filter
      const [list, sum, grp] = await Promise.all([
        workbenchApi.list(listStatus, 200),
        workbenchApi.summary(),
        workbenchApi.groups(),
      ])
      setItems(list.exceptions)
      setSummary(sum)
      setGroups(grp)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the queue.')
    } finally {
      setLoading(false)
    }
  }, [filter])

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

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Work<span className='text-gradient'>bench.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          Everything the agent refused to do on its own. Each item arrives with
          the evidence that stopped it and what it would have done instead.
        </p>
        <p className='mt-2 text-sm text-muted-foreground'>
          Nothing here is seeded. An empty queue means the Operators handled
          everything they saw.
        </p>
      </motion.div>

      <motion.div
        className='grid grid-cols-2 gap-4 lg:grid-cols-4'
        variants={itemVariants}
      >
        <Metric
          label='Awaiting a human'
          value={loading && !summary ? '…' : String(summary?.open ?? 0)}
          hint='blocked until someone decides'
        />
        <Metric
          label='Resolved'
          value={loading && !summary ? '…' : String(summary?.resolved ?? 0)}
          hint='decisions on the record'
        />
        <Metric
          label='Exception types'
          value={
            loading && !summary
              ? '…'
              : String(Object.keys(summary?.by_type ?? {}).length)
          }
          hint='distinct reasons the agent stopped'
        />
        <Metric
          label='Avg time to decision'
          value={
            loading && !summary
              ? '…'
              : summary?.avg_time_to_decision_seconds != null
                ? `${Math.round(summary.avg_time_to_decision_seconds / 60)}m`
                : '—'
          }
          hint={
            summary?.avg_time_to_decision_seconds == null
              ? 'nothing resolved yet'
              : 'raised to decided'
          }
        />
      </motion.div>

      <motion.div
        className='flex flex-wrap items-center gap-2'
        variants={itemVariants}
      >
        {(['open', 'classes', 'resolved', 'all'] as const).map((f) => (
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
            {f === 'classes'
              ? `By class${groups ? ` (${groups.group_count})` : ''}`
              : f}
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
        {error && <span className='text-xs text-red-600'>{error}</span>}
      </motion.div>

      {filter === 'classes' && groups && (
        <motion.div variants={itemVariants} className='space-y-3'>
          <p className='rounded-xl border border-border/60 bg-muted/20 px-4 py-3 text-xs text-muted-foreground'>
            <strong className='text-brand-navy'>
              {groups.items_in_groups} items fall into {groups.group_count}{' '}
              classes
            </strong>{' '}
            the Operators clustered themselves. Decide one and it applies to
            every item in it.{' '}
            <strong className='text-brand-navy'>
              {groups.ungrouped_items} stay individual
            </strong>{' '}
            — {groups.ungrouped_note}
          </p>

          {groups.groups.map((group) => (
            <GroupCard key={group.group_key} group={group} onChanged={load} />
          ))}
        </motion.div>
      )}

      {filter !== 'classes' && !loading && items.length === 0 && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-dashed border-border/60 py-12 text-center'
        >
          <p className='text-sm font-medium text-brand-navy'>
            {filter === 'open' ? 'Nothing awaiting a decision' : 'Nothing here'}
          </p>
          <p className='mx-auto mt-2 max-w-md text-xs text-muted-foreground'>
            Items appear when an Operator on Supervity Auto escalates something
            it will not do alone. Press “Sync from Auto” after a run.
          </p>
        </motion.div>
      )}

      {filter !== 'classes' && (
        <motion.div className='space-y-3' variants={itemVariants}>
          {items.map((item) => (
            <ExceptionCard key={item.id} item={item} onChanged={load} />
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}
