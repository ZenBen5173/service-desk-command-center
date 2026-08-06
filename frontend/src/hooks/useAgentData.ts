'use client'

import { useCallback, useEffect, useState } from 'react'

import {
  agentApi,
  type AgentMetrics,
  type AgentRun,
  type AgentStatus,
  type SyncResult,
} from '@/lib/agent'

interface UseAgentDataOptions {
  /** Poll interval in ms. Zero disables polling. */
  pollMs?: number
  runLimit?: number
}

interface UseAgentDataResult {
  status: AgentStatus | null
  metrics: AgentMetrics | null
  runs: AgentRun[]
  loading: boolean
  error: string | null
  syncing: boolean
  lastSync: SyncResult | null
  refresh: () => Promise<void>
  sync: () => Promise<void>
}

/**
 * Live agent data for the Command Center.
 *
 * `refresh` re-reads the backend mirror. `sync` pulls fresh data from Auto first
 * — that is the button to press on stage after triggering a run.
 */
export function useAgentData(
  options: UseAgentDataOptions = {}
): UseAgentDataResult {
  const { pollMs = 30000, runLimit = 25 } = options

  const [status, setStatus] = useState<AgentStatus | null>(null)
  const [metrics, setMetrics] = useState<AgentMetrics | null>(null)
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [lastSync, setLastSync] = useState<SyncResult | null>(null)

  const refresh = useCallback(async () => {
    try {
      // Status can fail on its own (Auto unreachable) without invalidating the
      // mirrored metrics, so it is settled separately rather than all-or-nothing.
      const [statusResult, metricsResult, runsResult] = await Promise.allSettled([
        agentApi.status(),
        agentApi.metrics(),
        agentApi.runs(runLimit),
      ])

      if (statusResult.status === 'fulfilled') setStatus(statusResult.value)
      if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value)
      if (runsResult.status === 'fulfilled') setRuns(runsResult.value.runs)

      const failed = [statusResult, metricsResult, runsResult].find(
        (r) => r.status === 'rejected'
      )
      if (failed && failed.status === 'rejected') {
        setError(
          failed.reason instanceof Error
            ? failed.reason.message
            : 'Could not reach the Command Center API.'
        )
      } else {
        setError(null)
      }
    } finally {
      setLoading(false)
    }
  }, [runLimit])

  const sync = useCallback(async () => {
    setSyncing(true)
    setError(null)
    try {
      const result = await agentApi.sync(40)
      setLastSync(result)
      await refresh()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Sync from Supervity Auto failed.'
      )
    } finally {
      setSyncing(false)
    }
  }, [refresh])

  useEffect(() => {
    void refresh()
    if (!pollMs) return
    const id = setInterval(() => void refresh(), pollMs)
    return () => clearInterval(id)
  }, [refresh, pollMs])

  return { status, metrics, runs, loading, error, syncing, lastSync, refresh, sync }
}
