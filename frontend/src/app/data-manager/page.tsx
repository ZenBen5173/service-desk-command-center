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
import { StatInfo } from '@/components/ui/stat-info'

interface Integration {
  key: string
  name: string
  category: string
  purpose: string
  endpoint: string | null
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  detail: string
  /** "direct" = probed just now. "inferred" = judged from recent agent runs. */
  check_type: 'direct' | 'inferred'
  checked_at: string
  workflows?: string[]
  workflow_count?: number
  runs_in_window?: number
  runs_succeeded?: number
  runs_failed?: number
  last_used_at?: string | null
}

interface Registry {
  integrations: Integration[]
  totals: {
    count: number
    healthy: number
    degraded: number
    down: number
    unknown: number
    categories: number
  }
  categories: string[]
  evidence_window_days: number
  excluded_as_libraries: string[]
  generated_at: string
  warnings: string[]
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

const STATUS_TONE: Record<Integration['status'], string> = {
  healthy: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  degraded: 'bg-amber-50 text-amber-700 border-amber-200',
  down: 'bg-red-50 text-red-700 border-red-200',
  unknown: 'bg-slate-50 text-slate-600 border-slate-200',
}

const STATUS_DOT: Record<Integration['status'], string> = {
  healthy: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  down: 'bg-red-500',
  unknown: 'bg-slate-400',
}

function Metric({
  label,
  value,
  hint,
  explain,
}: {
  label: string
  value: string
  hint?: string
  explain?: React.ReactNode
}) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={0.9} />
      <CardContent className='relative z-10 p-5'>
        <div className='flex items-start justify-between gap-2'>
          <p className='text-micro uppercase text-brand-muted'>{label}</p>
          {explain && <StatInfo>{explain}</StatInfo>}
        </div>
        <p className='mt-2 font-display text-[2rem] font-bold leading-none text-brand-navy'>
          {value}
        </p>
        {hint && <p className='mt-2 text-xs text-muted-foreground'>{hint}</p>}
      </CardContent>
    </Card>
  )
}

function IntegrationCard({ item }: { item: Integration }) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={1} />
      <CardContent className='relative z-10 space-y-3 p-4'>
        <div className='flex items-start justify-between gap-3'>
          <div className='min-w-0'>
            <p className='text-micro uppercase text-brand-muted'>
              {item.category}
            </p>
            <h3 className='mt-0.5 font-display text-base font-bold text-brand-navy'>
              {item.name}
            </h3>
          </div>
          <span
            className={cn(
              'flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize',
              STATUS_TONE[item.status]
            )}
          >
            <span
              className={cn('h-1.5 w-1.5 rounded-full', STATUS_DOT[item.status])}
            />
            {item.status}
          </span>
        </div>

        <p className='text-xs text-muted-foreground'>{item.purpose}</p>

        <div className='rounded-lg bg-muted/30 p-2.5'>
          <p className='text-xs text-brand-navy'>{item.detail}</p>
          {/* An inferred status must never be mistaken for a live probe. */}
          <p className='mt-1 text-[11px] text-muted-foreground'>
            {item.check_type === 'direct'
              ? 'Checked directly just now'
              : 'Inferred from recent agent runs — this connection belongs to the Operators on Auto, not to this backend'}
          </p>
        </div>

        {item.endpoint && (
          <p className='truncate font-mono text-[11px] text-muted-foreground'>
            {item.endpoint}
          </p>
        )}

        {item.workflows && item.workflows.length > 0 && (
          <div>
            <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
              Used by
            </p>
            <div className='flex flex-wrap gap-1'>
              {item.workflows.map((w, i) => (
                <span
                  key={`${w}-${i}`}
                  className='rounded border border-border/50 bg-white/70 px-1.5 py-0.5 text-[11px] text-muted-foreground'
                >
                  {w}
                </span>
              ))}
            </div>
          </div>
        )}

        {item.last_used_at && (
          <p className='text-[11px] text-muted-foreground'>
            Last used {formatRelative(item.last_used_at)}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default function DataManagerPage() {
  const [registry, setRegistry] = useState<Registry | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRegistry(await apiClient.get<Registry>('/api/integrations'))
      setError(null)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not load the registry.'
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

  const totals = registry?.totals

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Data <span className='text-gradient'>Manager.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          Every system this Command Center depends on, and whether it is
          actually working.
        </p>
        <p className='mt-2 max-w-3xl text-sm text-muted-foreground'>
          This list is discovered, not declared. It comes from the services each
          workflow on Supervity Auto reports, so connecting a new system in Auto
          makes it appear here with no code change.
        </p>
      </motion.div>

      <motion.div
        className='flex flex-wrap items-center gap-3'
        variants={itemVariants}
      >
        <Button onClick={() => void load()} variant='outline' size='sm'>
          <Icons.activity className='mr-2 h-4 w-4' strokeWidth={1.5} />
          Re-check now
        </Button>
        {registry && (
          <span className='text-xs text-muted-foreground'>
            Checked {formatRelative(registry.generated_at)}
          </span>
        )}
        {error && <span className='text-xs text-red-600'>{error}</span>}
      </motion.div>

      <motion.div
        className='grid grid-cols-2 gap-4 lg:grid-cols-4'
        variants={itemVariants}
      >
        <Metric
          label='Integrations'
          explain="Discovered from the services each workflow on Auto declares, not from a list typed here. Connect something new there and it appears."
          value={loading && !totals ? '…' : String(totals?.count ?? 0)}
          hint={`across ${totals?.categories ?? 0} categories`}
        />
        <Metric
          label='Healthy'
          explain="Nothing using this service has failed in the last hour. The card shows the full history, so an older failure is still visible."
          value={loading && !totals ? '…' : String(totals?.healthy ?? 0)}
          hint='working right now'
        />
        <Metric
          label='Degraded'
          explain="Something using this service failed within the last hour. Older failures stay in the counts but no longer set the status."
          value={loading && !totals ? '…' : String(totals?.degraded ?? 0)}
          hint='some recent runs failed'
        />
        <Metric
          label='Down'
          explain="Every recent run using this service failed. Not the same as degraded, which is some."
          value={loading && !totals ? '…' : String(totals?.down ?? 0)}
          hint='not reachable'
        />
      </motion.div>

      {registry?.warnings.map((w) => (
        <motion.div
          key={w}
          variants={itemVariants}
          className='rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800'
        >
          {w}
        </motion.div>
      ))}

      <motion.div
        className='grid gap-4 md:grid-cols-2 xl:grid-cols-3'
        variants={itemVariants}
      >
        {registry?.integrations.map((item) => (
          <IntegrationCard key={item.key} item={item} />
        ))}
      </motion.div>

      {registry && registry.excluded_as_libraries.length > 0 && (
        <motion.div
          variants={itemVariants}
          className='rounded-xl border border-border/50 bg-white/60 p-4'
        >
          <p className='text-sm font-medium text-brand-navy'>
            Not counted as integrations
          </p>
          <p className='mt-1 text-xs text-muted-foreground'>
            Supervity Auto lists a workflow&apos;s code libraries and file
            formats alongside its real connections. These are runtime
            dependencies, not systems, so they are excluded — listed here so the
            filtering is visible rather than silent:{' '}
            <span className='font-mono'>
              {registry.excluded_as_libraries.join(', ')}
            </span>
          </p>
        </motion.div>
      )}

      {registry && (
        <motion.p
          variants={itemVariants}
          className='text-xs text-muted-foreground'
        >
          Health for Operator-owned connections is judged over the last{' '}
          {registry.evidence_window_days} days of agent runs. Those systems are
          reached by the Operators on Auto using their own credentials, so this
          backend has nothing to probe directly and does not pretend otherwise.
        </motion.p>
      )}
    </motion.div>
  )
}
