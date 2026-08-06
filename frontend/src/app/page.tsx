'use client'

import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { AgentActivityChart } from '@/components/agent/AgentActivityChart'
import { BusinessOutcomes } from '@/components/agent/BusinessOutcomes'
import { AgentRunsPanel } from '@/components/agent/AgentRunsPanel'
import { AgentStatusBar } from '@/components/agent/AgentStatusBar'
import { useAgentData } from '@/hooks/useAgentData'
import { formatDuration } from '@/lib/agent'
import { cn } from '@/lib/utils'

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      ease: [0.25, 0.46, 0.45, 0.94],
    },
  },
}

// Animated number component
function AnimatedNumber({
  value,
  suffix = '',
  duration = 1000,
}: {
  value: number
  suffix?: string
  duration?: number
}) {
  const [displayValue, setDisplayValue] = useState(0)
  // Mirror of displayValue for the animation to read without re-subscribing.
  const shownRef = useRef(0)
  shownRef.current = displayValue

  // Two deliberate choices here, both learned the hard way:
  //
  // 1. No in-view gate. These cards carry the headline figures. An
  //    IntersectionObserver that never fires — background tab, non-compositing
  //    viewport — would leave them showing a zero that reads as real data.
  // 2. No "already animated" ref guard. React StrictMode double-invokes effects
  //    in development: the first pass would claim the value, the cleanup would
  //    cancel its timer, and the second pass would early-return having done
  //    nothing — pinning the card at zero. Animating from whatever is currently
  //    shown is idempotent, so a double-invoke is harmless.
  useEffect(() => {
    const from = shownRef.current
    if (from === value) return

    const startTime = performance.now()
    let raf = 0
    let done = false

    const animate = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(2, -10 * progress)
      setDisplayValue(Math.round(from + eased * (value - from)))
      if (progress < 1) {
        raf = requestAnimationFrame(animate)
      } else {
        done = true
        setDisplayValue(value)
      }
    }
    raf = requestAnimationFrame(animate)

    // requestAnimationFrame is paused entirely in background or non-compositing
    // tabs. The number matters more than the count-up, so land on it regardless.
    const settle = setTimeout(() => {
      if (!done) setDisplayValue(value)
    }, duration + 150)

    return () => {
      cancelAnimationFrame(raf)
      clearTimeout(settle)
    }
  }, [value, duration])

  const formatValue = (num: number): string => {
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
  }

  return (
    <span>
      {formatValue(displayValue)}
      {suffix}
    </span>
  )
}

// Stats Card Component with Bento styling
interface StatCardProps {
  title: string
  /** Null means "no data yet" — rendered as a dash, never as a zero. */
  value: number | null
  suffix?: string
  icon: React.ElementType
  /** Small line under the number: context, not a fabricated trend. */
  footnote?: string
  colorClass: string
  delay?: number
  loading?: boolean
}

function StatCard({
  title,
  value,
  suffix = '',
  icon: Icon,
  footnote,
  colorClass,
  delay = 0,
  loading = false,
}: StatCardProps) {
  return (
    <motion.div
      variants={itemVariants}
      initial='hidden'
      animate='visible'
      transition={{ delay }}
      whileHover={{ y: -4 }}
    >
      <Card className='group relative h-full cursor-default overflow-hidden'>
        {/* Branded watermark texture */}
        <CardWatermark opacity={3} scale={0.9} />
        <CardContent className='relative z-10 p-5'>
          <div className='flex items-start justify-between'>
            <div className='space-y-2'>
              {/* Micro label */}
              <p className='text-micro uppercase text-brand-muted transition-colors duration-200 group-hover:text-brand-cornflower'>
                {title}
              </p>
              {/* Display number */}
              <p className='font-display text-[2.25rem] font-bold leading-none tracking-tight text-brand-navy'>
                {loading ? (
                  <span className='text-brand-muted'>…</span>
                ) : value === null ? (
                  <span className='text-brand-muted'>—</span>
                ) : (
                  <AnimatedNumber value={value} suffix={suffix} />
                )}
              </p>
              {footnote && (
                <motion.p
                  className='text-xs font-medium text-muted-foreground'
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: delay + 0.3 }}
                >
                  {footnote}
                </motion.p>
              )}
            </div>
            {/* Icon */}
            <motion.div
              className={cn(
                'rounded-xl p-2.5 text-white',
                'shadow-lg',
                colorClass
              )}
              whileHover={{ scale: 1.15, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 400, damping: 17 }}
            >
              <Icon className='h-5 w-5' strokeWidth={1.5} />
            </motion.div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

// Hero Section
function HeroSection() {
  return (
    <motion.div
      className='col-span-12 py-2'
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      <h1 className='text-display-3 font-bold tracking-tight text-brand-navy lg:text-display-2'>
        Service Desk <br className='hidden sm:block' />
        <span className='text-gradient'>Command Center.</span>
      </h1>
      <p className='mt-4 text-lg font-light text-muted-foreground'>
        Governing an AI service desk that eliminates problems, not just tickets.
      </p>
    </motion.div>
  )
}

// Operator roster — which agents exist on Auto and how much work each did
function OperatorBreakdown({
  metrics,
  loading,
}: {
  metrics: ReturnType<typeof useAgentData>['metrics']
  loading: boolean
}) {
  const rows = metrics?.by_workflow ?? []

  return (
    <Card className='relative col-span-12 h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={1.1} />
      <CardContent className='relative z-10 p-5'>
        <div className='mb-4'>
          <h2 className='flex items-center gap-2 font-display text-lg font-bold text-brand-navy'>
            <Icons.users className='h-5 w-5 text-brand-cornflower' strokeWidth={1.5} />
            Agent Roster
          </h2>
          <p className='mt-1 text-sm text-muted-foreground'>
            Runs per Orchestrator and Operator, straight from Supervity Auto.
          </p>
        </div>

        {loading && rows.length === 0 && (
          <p className='py-4 text-sm text-muted-foreground'>Loading roster…</p>
        )}

        {!loading && rows.length === 0 && (
          <p className='py-4 text-sm text-muted-foreground'>
            Nothing mirrored yet. Press “Sync from Auto”.
          </p>
        )}

        <div className='space-y-2'>
          {rows.map((row) => {
            const share = metrics?.total_runs
              ? Math.round((row.runs / metrics.total_runs) * 100)
              : 0
            return (
              <div key={row.workflow_name} className='space-y-1'>
                <div className='flex items-center justify-between gap-3 text-sm'>
                  <span className='min-w-0 flex-1 truncate font-medium text-brand-navy'>
                    {row.workflow_name}
                  </span>
                  <span className='shrink-0 text-xs text-muted-foreground'>
                    {row.runs} run{row.runs === 1 ? '' : 's'}
                    {row.failed > 0 && (
                      <span className='ml-1 text-red-500'>· {row.failed} failed</span>
                    )}
                  </span>
                </div>
                <div className='h-1.5 w-full overflow-hidden rounded-full bg-muted'>
                  <motion.div
                    className='h-full rounded-full bg-brand-cornflower'
                    initial={{ width: 0 }}
                    animate={{ width: `${share}%` }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// Main Dashboard — no auth required, renders directly
export default function HomePage() {
  const { status, metrics, runs, loading, error, syncing, lastSync, sync } =
    useAgentData({ pollMs: 30000, runLimit: 25 })

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Hero Section */}
      <HeroSection />

      {/* Provenance strip — makes it plain these numbers come from Auto */}
      <motion.div variants={itemVariants}>
        <AgentStatusBar
          status={status}
          lastRunAt={metrics?.last_run_at}
          syncing={syncing}
          lastSync={lastSync}
          error={error}
          onSync={() => void sync()}
        />
      </motion.div>

      {/* Stats Grid — every value computed from real agent runs */}
      <div className='grid grid-cols-2 gap-4 lg:grid-cols-4'>
        <StatCard
          title='Agent Runs'
          value={metrics?.total_runs ?? null}
          icon={Icons.activity}
          footnote={
            metrics
              ? `${metrics.completed_runs} completed · ${metrics.failed_runs} failed`
              : undefined
          }
          colorClass='bg-brand-navy'
          delay={0.1}
          loading={loading}
        />
        <StatCard
          title='Success Rate'
          value={metrics?.success_rate_pct ?? null}
          suffix='%'
          icon={Icons.checkCircle}
          footnote={
            metrics?.success_rate_pct === null
              ? 'no finished runs yet'
              : 'of all finished runs'
          }
          colorClass='bg-brand-purple'
          delay={0.2}
          loading={loading}
        />
        <StatCard
          title='Avg Run Time'
          value={metrics?.avg_duration_seconds ?? null}
          suffix='s'
          icon={Icons.clock}
          footnote={
            metrics?.avg_duration_seconds != null
              ? formatDuration(Math.round(metrics.avg_duration_seconds))
              : undefined
          }
          colorClass='bg-brand-cornflower'
          delay={0.3}
          loading={loading}
        />
        <StatCard
          title='Operators Live'
          value={metrics?.operator_count ?? null}
          icon={Icons.sparkles}
          footnote={
            metrics
              ? `+ ${metrics.orchestrator_count} orchestrator${metrics.orchestrator_count === 1 ? '' : 's'}`
              : undefined
          }
          colorClass='bg-gradient-to-br from-brand-navy to-brand-purple'
          delay={0.4}
          loading={loading}
        />
      </div>

      {/* The judged figures, above the fold */}
      <motion.div variants={itemVariants}>
        <BusinessOutcomes />
      </motion.div>

      {/* Run history from real runs */}
      <motion.div variants={itemVariants}>
        <AgentActivityChart runs={runs} />
      </motion.div>

      {/* Roster + activity timeline */}
      <motion.div className='grid gap-6 lg:grid-cols-12' variants={itemVariants}>
        <OperatorBreakdown metrics={metrics} loading={loading} />
      </motion.div>

      <motion.div variants={itemVariants}>
        <AgentRunsPanel runs={runs} loading={loading} />
      </motion.div>
    </motion.div>
  )
}
