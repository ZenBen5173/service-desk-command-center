'use client'

import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'

import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { businessApi, type BusinessMetrics } from '@/lib/business'
import { cn } from '@/lib/utils'

/**
 * The four judged metrics, plus deflection.
 *
 * Every tile shows which Operator produced its number. A metric no Operator has
 * reported renders as a dash with the reason — never as a zero, because a zero
 * is a claim and a dash is the truth.
 */
function Tile({
  label,
  value,
  suffix,
  hint,
  source,
  accent,
  muted,
}: {
  label: string
  value: string
  suffix?: string
  hint?: string
  source?: string
  accent?: boolean
  muted?: boolean
}) {
  return (
    <Card className='relative h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={0.9} />
      <CardContent className='relative z-10 flex h-full flex-col p-4'>
        <p className='text-micro uppercase text-brand-muted'>{label}</p>
        <p
          className={cn(
            'mt-1.5 font-display text-[1.75rem] font-bold leading-none tracking-tight',
            muted ? 'text-brand-muted' : accent ? 'text-gradient' : 'text-brand-navy'
          )}
        >
          {value}
          {suffix && !muted && (
            <span className='ml-0.5 text-base font-semibold'>{suffix}</span>
          )}
        </p>
        {hint && (
          <p className='mt-1.5 text-xs leading-snug text-muted-foreground'>{hint}</p>
        )}
        {source && (
          <p
            className='mt-auto pt-2 text-[10px] leading-tight text-brand-muted'
            title={`Reported by ${source}`}
          >
            via {source.replace(' Operator', '')}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function BusinessOutcomes({ className }: { className?: string }) {
  const [metrics, setMetrics] = useState<BusinessMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setMetrics(await businessApi.metrics())
    } catch {
      // The dashboard still works without this panel; it simply shows nothing.
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 30000)
    return () => clearInterval(id)
  }, [load])

  const dash = loading ? '…' : '—'
  const { csat, sla, resolution, deflection, knowledge, sources } = metrics ?? {}

  return (
    <div className={cn('space-y-3', className)}>
      <div>
        <h2 className='flex items-center gap-2 font-display text-lg font-bold text-brand-navy'>
          <Icons.target
            className='h-5 w-5 text-brand-cornflower'
            strokeWidth={1.5}
          />
          Business Outcomes
        </h2>
        <p className='mt-1 text-sm text-muted-foreground'>
          The figures this is judged on, as the Operators reported them. Each
          tile names the agent it came from.
        </p>
      </div>

      <motion.div
        className='grid grid-cols-2 gap-3 lg:grid-cols-5'
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <Tile
          label='CSAT'
          value={csat ? csat.average.toFixed(2) : dash}
          suffix={csat ? '/5' : undefined}
          muted={!csat}
          hint={
            csat
              ? `${csat.responses ?? 0} responses · ${csat.response_rate_pct ?? 0}% replied`
              : 'no satisfaction data reported yet'
          }
          source={sources?.csat}
        />

        <Tile
          label='SLA on Calendar'
          value={sla ? String(sla.authoritative_pct) : dash}
          suffix={sla ? '%' : undefined}
          muted={!sla}
          hint={
            sla
              ? `${sla.on_business_hours} of ${sla.tickets_measured} measured on business hours`
              : 'no SLA basis reported yet'
          }
          source={sources?.sla}
        />

        <Tile
          label='Auto-resolution'
          value={resolution ? String(resolution.auto_resolution_rate_pct) : dash}
          suffix={resolution ? '%' : undefined}
          muted={!resolution}
          hint={
            resolution
              ? `${resolution.allowed} allowed · ${resolution.human_review} to review` +
                (resolution.acted_on !== undefined
                  ? ` · ${resolution.acted_on} acted on, ${resolution.cleared_awaiting_action} awaiting action`
                  : '') +
                (resolution.basis === 'individual_operator_runs'
                  ? ' · from single-ticket runs, not a full cycle'
                  : ` · across ${resolution.decisions} ticket${resolution.decisions === 1 ? '' : 's'} this cycle`)
              : 'no decisions recorded yet'
          }
          source={sources?.resolution}
        />

        <Tile
          label='Collapsed Now'
          value={
            deflection?.collapsed_now
              ? String(deflection.collapsed_now.count)
              : dash
          }
          muted={!deflection?.collapsed_now}
          accent
          hint={
            deflection?.collapsed_now
              ? 'tickets that became one incident — work already avoided'
              : 'no correlation reported yet'
          }
          source={sources?.deflection}
        />

        <Tile
          label='Preventable'
          value={
            deflection?.preventable ? String(deflection.preventable.count) : dash
          }
          muted={!deflection?.preventable}
          accent
          hint={
            deflection?.preventable
              ? `forecast, if the ${knowledge?.articles_drafted ?? 0} proposed fixes ship`
              : 'no forecast reported yet'
          }
          source={sources?.deflection}
        />
      </motion.div>

      {/* MTTR is absent by choice, and says so rather than showing a made-up
          figure. Better to be asked about a gap than caught inventing one. */}
      {metrics?.mttr === null && (
        <p className='text-xs text-muted-foreground'>
          <strong className='text-brand-navy'>MTTR is not shown.</strong>{' '}
          {metrics.mttr_note}
        </p>
      )}
    </div>
  )
}
