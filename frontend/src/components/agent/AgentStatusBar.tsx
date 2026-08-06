'use client'

import { motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { type AgentStatus, type SyncResult, formatRelative } from '@/lib/agent'
import { cn } from '@/lib/utils'

interface AgentStatusBarProps {
  status: AgentStatus | null
  lastRunAt: string | null | undefined
  syncing: boolean
  lastSync: SyncResult | null
  error: string | null
  onSync: () => void
  className?: string
}

/**
 * The provenance strip. Its job is to make it obvious at a glance that the
 * numbers below come from Supervity Auto and not from the template's demo data.
 */
export function AgentStatusBar({
  status,
  lastRunAt,
  syncing,
  lastSync,
  error,
  onSync,
  className,
}: AgentStatusBarProps) {
  const connected = Boolean(status?.healthy)
  const configured = status?.configured ?? false

  const label = !configured
    ? 'Not connected — no API key'
    : connected
      ? 'Live from Supervity Auto'
      : 'Auto unreachable'

  const tone = !configured
    ? 'bg-amber-50 text-amber-700 border-amber-200'
    : connected
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : 'bg-red-50 text-red-600 border-red-200'

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-border/50 bg-white/60 px-4 py-3 backdrop-blur-sm',
        className
      )}
    >
      <div
        className={cn(
          'flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium',
          tone
        )}
      >
        <span className='relative flex h-2 w-2'>
          {connected && (
            <motion.span
              className='absolute inline-flex h-full w-full rounded-full bg-emerald-400'
              animate={{ opacity: [0.8, 0, 0.8], scale: [1, 2, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}
          <span
            className={cn(
              'relative inline-flex h-2 w-2 rounded-full',
              connected
                ? 'bg-emerald-500'
                : configured
                  ? 'bg-red-500'
                  : 'bg-amber-500'
            )}
          />
        </span>
        {label}
      </div>

      {status && (
        <div className='flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground'>
          <span>
            <span className='font-semibold text-brand-navy'>
              {status.mirrored.orchestrators}
            </span>{' '}
            orchestrator{status.mirrored.orchestrators === 1 ? '' : 's'}
          </span>
          <span>
            <span className='font-semibold text-brand-navy'>
              {status.mirrored.operators}
            </span>{' '}
            operators
          </span>
          <span>
            <span className='font-semibold text-brand-navy'>
              {status.mirrored.runs}
            </span>{' '}
            runs mirrored
          </span>
          <span>Last agent run {formatRelative(lastRunAt)}</span>
        </div>
      )}

      <div className='ml-auto flex items-center gap-3'>
        {lastSync && !syncing && (
          <span className='text-xs text-muted-foreground'>
            Synced {lastSync.runs?.runs_seen ?? 0} runs
            {lastSync.timelines.unavailable_on_auto > 0 && (
              <span
                className='ml-1 text-amber-600'
                title='Auto lists these runs but no longer serves their step-by-step timeline.'
              >
                ({lastSync.timelines.unavailable_on_auto} timelines unavailable)
              </span>
            )}
          </span>
        )}
        <Button
          onClick={onSync}
          disabled={syncing || !configured}
          variant='outline'
          size='sm'
        >
          <Icons.activity
            className={cn('mr-2 h-4 w-4', syncing && 'animate-spin')}
            strokeWidth={1.5}
          />
          {syncing ? 'Syncing…' : 'Sync from Auto'}
        </Button>
      </div>

      {(error || (status && !status.healthy && status.detail)) && (
        <p className='w-full text-xs text-red-600'>
          {error || status?.detail}
        </p>
      )}
    </div>
  )
}
