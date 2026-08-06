'use client'

import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { type AgentRun } from '@/lib/agent'
import { cn } from '@/lib/utils'

interface DayBucket {
  name: string
  iso: string
  completed: number
  failed: number
  total: number
}

/**
 * Local-calendar day key, e.g. "2026-07-18".
 *
 * Deliberately not `toISOString().slice(0, 10)`: that converts to UTC first, so
 * for a viewer east of Greenwich a run at 09:00 local lands on the previous
 * day's key. Bucket keys and run keys must be derived the same way or every run
 * falls outside the window.
 */
function dayKey(d: Date): string {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Buckets real agent runs by day.
 *
 * The window is derived from the runs themselves, not from today's date. Agent
 * activity may have happened days ago, and a fixed "last 7 days" window would
 * render an empty chart and look broken.
 */
function bucketRuns(runs: AgentRun[], maxDays: number): DayBucket[] {
  const dated = runs.filter((r) => r.started_at)
  if (dated.length === 0) return []

  const times = dated.map((r) => new Date(r.started_at as string).getTime())
  const latest = new Date(Math.max(...times))
  latest.setHours(0, 0, 0, 0)
  const earliest = new Date(Math.min(...times))
  earliest.setHours(0, 0, 0, 0)

  // Size the window to the data rather than to a fixed "last 14 days". Agent
  // runs may all sit weeks back, and a fixed recent window renders empty.
  const spanDays =
    Math.round((latest.getTime() - earliest.getTime()) / 86400000) + 1
  const days = Math.max(7, Math.min(spanDays, maxDays))

  const buckets = new Map<string, DayBucket>()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(latest)
    d.setDate(d.getDate() - i)
    const key = dayKey(d)
    buckets.set(key, {
      iso: key,
      name: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      completed: 0,
      failed: 0,
      total: 0,
    })
  }

  for (const run of dated) {
    const key = dayKey(new Date(run.started_at as string))
    const bucket = buckets.get(key)
    if (!bucket) continue // Outside the window — counted in totals elsewhere.
    bucket.total += 1
    const status = (run.status || '').toLowerCase()
    if (status === 'completed') bucket.completed += 1
    else if (status === 'failed' || status === 'error') bucket.failed += 1
  }

  return Array.from(buckets.values())
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className='rounded-xl border border-white/60 bg-white/95 p-3 shadow-float backdrop-blur-sm'>
      <p className='mb-2 text-xs font-medium text-brand-navy'>{label}</p>
      <div className='space-y-1'>
        {payload.map((entry, i) => (
          <div key={i} className='flex items-center gap-2 text-xs'>
            <div
              className='h-2 w-2 rounded-full'
              style={{ backgroundColor: entry.color }}
            />
            <span className='text-muted-foreground'>{entry.name}:</span>
            <span className='font-semibold text-brand-navy'>{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

interface AgentActivityChartProps {
  runs: AgentRun[]
  /** Upper bound on the window. The actual window shrinks to fit the data. */
  maxDays?: number
  className?: string
}

export function AgentActivityChart({
  runs,
  maxDays = 45,
  className,
}: AgentActivityChartProps) {
  const data = useMemo(() => bucketRuns(runs, maxDays), [runs, maxDays])
  const days = data.length

  const inWindow = data.reduce((acc, d) => acc + d.total, 0)
  const undated = runs.filter((r) => !r.started_at).length
  const outsideWindow = runs.length - inWindow - undated

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardWatermark opacity={4} scale={1.2} />

      <CardHeader className='pb-2'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <CardTitle className='flex items-center gap-2'>
              <Icons.activity
                className='h-5 w-5 text-brand-cornflower'
                strokeWidth={1.5}
              />
              Agent Run History
            </CardTitle>
            <p className='mt-1 text-sm text-muted-foreground'>
              Real runs on Supervity Auto, bucketed by day.
            </p>
          </div>

          {data.length > 0 && (
            <div className='flex items-center gap-4'>
              <div className='text-right'>
                <p className='text-micro uppercase text-brand-muted'>
                  Runs in window
                </p>
                <p className='font-display text-lg font-bold text-brand-navy'>
                  {inWindow}
                </p>
              </div>
              <div className='h-10 w-px bg-border/50' />
              <div className='text-right'>
                <p className='text-micro uppercase text-brand-muted'>Window</p>
                <p className='font-display text-lg font-bold text-brand-navy'>
                  {days}d
                </p>
              </div>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className='pt-0'>
        {data.length === 0 ? (
          <div className='flex h-[200px] items-center justify-center rounded-xl border border-dashed border-border/60'>
            <div className='text-center'>
              <p className='text-sm font-medium text-brand-navy'>
                No dated agent runs yet
              </p>
              <p className='mt-1 text-xs text-muted-foreground'>
                Sync from Auto, or trigger a run to populate this chart.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className='mt-4 h-[220px] w-full'>
              <ResponsiveContainer width='100%' height='100%'>
                <AreaChart
                  data={data}
                  margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id='gradCompleted' x1='0' y1='0' x2='0' y2='1'>
                      <stop offset='0%' stopColor='#5B8DEF' stopOpacity={0.4} />
                      <stop offset='95%' stopColor='#5B8DEF' stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id='gradFailed' x1='0' y1='0' x2='0' y2='1'>
                      <stop offset='0%' stopColor='#EF4444' stopOpacity={0.3} />
                      <stop offset='95%' stopColor='#EF4444' stopOpacity={0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid
                    strokeDasharray='3 3'
                    stroke='rgba(20, 26, 66, 0.06)'
                    vertical={false}
                  />
                  <XAxis
                    dataKey='name'
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#7B8AB8', fontSize: 11, fontWeight: 500 }}
                    dy={8}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                    tick={{ fill: '#7B8AB8', fontSize: 11 }}
                  />
                  <Tooltip content={<ChartTooltip />} />

                  <Area
                    type='monotone'
                    dataKey='completed'
                    name='Completed'
                    stroke='#5B8DEF'
                    strokeWidth={2.5}
                    fill='url(#gradCompleted)'
                    dot={{ r: 3, fill: '#5B8DEF' }}
                  />
                  <Area
                    type='monotone'
                    dataKey='failed'
                    name='Failed'
                    stroke='#EF4444'
                    strokeWidth={2}
                    fill='url(#gradFailed)'
                    dot={{ r: 3, fill: '#EF4444' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className='mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 border-t border-border/30 pt-4'>
              <div className='flex items-center gap-2'>
                <div className='h-2 w-2 rounded-full bg-brand-cornflower' />
                <span className='text-xs text-muted-foreground'>Completed</span>
              </div>
              <div className='flex items-center gap-2'>
                <div className='h-2 w-2 rounded-full bg-red-500' />
                <span className='text-xs text-muted-foreground'>Failed</span>
              </div>
              {/* Anything the chart cannot show is stated, never quietly dropped. */}
              {(outsideWindow > 0 || undated > 0) && (
                <span className='text-xs text-muted-foreground'>
                  {outsideWindow > 0 && `${outsideWindow} run(s) outside window`}
                  {outsideWindow > 0 && undated > 0 && ' · '}
                  {undated > 0 && `${undated} run(s) with no start time`}
                </span>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
