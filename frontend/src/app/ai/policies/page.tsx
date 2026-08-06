'use client'

import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { formatRelative } from '@/lib/agent'
import {
  outcomeTone,
  policiesApi,
  type EffectiveInputs,
  type EvaluationSummary,
  type Policy,
  type PolicyChange,
  type PolicyEvaluation,
  type PolicyParameter,
} from '@/lib/policies'
import { cn } from '@/lib/utils'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.06 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

type ParamValue = number | boolean | string

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
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

function ParameterField({
  param,
  draft,
  onChange,
}: {
  param: PolicyParameter
  draft: ParamValue
  onChange: (value: ParamValue) => void
}) {
  const dirty = draft !== param.value

  return (
    <div className='space-y-1.5 rounded-lg border border-border/50 bg-white/60 p-3'>
      <div className='flex items-start justify-between gap-3'>
        <div className='min-w-0 flex-1'>
          <p className='text-sm font-medium text-brand-navy'>{param.label}</p>
          {param.help && (
            <p className='mt-0.5 text-xs text-muted-foreground'>{param.help}</p>
          )}
        </div>

        <div className='shrink-0'>
          {param.type === 'boolean' ? (
            <Switch
              checked={Boolean(draft)}
              onCheckedChange={(checked) => onChange(checked)}
            />
          ) : param.type === 'number' ? (
            <Input
              type='number'
              className='w-28 text-right'
              value={String(draft)}
              min={param.min}
              max={param.max}
              step={param.step ?? 'any'}
              onChange={(e) => onChange(e.target.value)}
            />
          ) : (
            <Input
              className='w-44'
              value={String(draft)}
              onChange={(e) => onChange(e.target.value)}
            />
          )}
        </div>
      </div>

      <div className='flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground'>
        {param.maps_to_input && (
          <span
            className='font-mono'
            title='The Supervity Auto workflow input this value is passed to.'
          >
            → {param.maps_to_input}
          </span>
        )}
        <span>default {String(param.default)}</span>
        {param.type === 'number' && param.min !== undefined && (
          <span>
            range {param.min}–{param.max}
          </span>
        )}
        {dirty && (
          <span className='font-medium text-amber-600'>
            unsaved: {String(param.value)} → {String(draft)}
          </span>
        )}
      </div>
    </div>
  )
}

function PolicyPanel({
  policy,
  onSaved,
}: {
  policy: Policy
  onSaved: () => void
}) {
  const [open, setOpen] = useState(false)
  const [drafts, setDrafts] = useState<Record<string, ParamValue>>({})
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [problems, setProblems] = useState<string[]>([])

  // Re-seed drafts whenever the saved policy changes, so a save or a reset
  // elsewhere is reflected instead of leaving stale edits on screen.
  useEffect(() => {
    const seeded: Record<string, ParamValue> = {}
    for (const param of policy.parameters) seeded[param.name] = param.value
    setDrafts(seeded)
  }, [policy])

  const dirty = policy.parameters.some((p) => drafts[p.name] !== p.value)

  const save = async () => {
    setSaving(true)
    setFeedback(null)
    setProblems([])
    try {
      const changes: Record<string, ParamValue> = {}
      for (const param of policy.parameters) {
        if (drafts[param.name] !== param.value) changes[param.name] = drafts[param.name]
      }
      const result = await policiesApi.update(policy.key, {
        parameters: changes,
        note: 'edited in the Command Center',
      })
      if (result.rejected.length > 0) {
        setProblems(
          result.rejected.map((r) => `${r.parameter}: ${r.reason}`)
        )
      }
      if (result.changed.length > 0) {
        setFeedback(
          `Saved. In force on the next agent run: ${result.changed
            .map((c) => c.replace('parameters.', ''))
            .join(', ')}.`
        )
      }
      onSaved()
    } catch (err) {
      setProblems([err instanceof Error ? err.message : 'Save failed.'])
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    setSaving(true)
    try {
      await policiesApi.reset(policy.key)
      setFeedback('Reset to defaults.')
      onSaved()
    } catch (err) {
      setProblems([err instanceof Error ? err.message : 'Reset failed.'])
    } finally {
      setSaving(false)
    }
  }

  const toggleEnabled = async (enabled: boolean) => {
    setSaving(true)
    try {
      await policiesApi.update(policy.key, { enabled, note: 'toggled in the UI' })
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className='relative overflow-hidden'>
      <CardWatermark opacity={3} scale={1} />
      <CardContent className='relative z-10 p-5'>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <button
            onClick={() => setOpen(!open)}
            className='min-w-0 flex-1 text-left'
          >
            <div className='flex flex-wrap items-center gap-2'>
              <h3 className='font-display text-base font-bold text-brand-navy'>
                {policy.name}
              </h3>
              {policy.category && (
                <span className='rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground'>
                  {policy.category}
                </span>
              )}
              {!policy.enabled && (
                <span className='rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-500'>
                  Disabled
                </span>
              )}
              <Icons.chevronDown
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  open && 'rotate-180'
                )}
              />
            </div>
            {policy.description && (
              <p className='mt-1.5 max-w-3xl text-sm text-muted-foreground'>
                {policy.description}
              </p>
            )}
          </button>

          <div className='flex shrink-0 items-center gap-2'>
            <span className='text-xs text-muted-foreground'>Active</span>
            <Switch
              checked={policy.enabled}
              disabled={saving}
              onCheckedChange={toggleEnabled}
            />
          </div>
        </div>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className='overflow-hidden'
            >
              <div className='mt-4 space-y-4'>
                {policy.rule_text && (
                  <div className='rounded-lg border border-border/50 bg-muted/20 p-3'>
                    <p className='mb-1 text-[10px] font-semibold uppercase tracking-wide text-brand-muted'>
                      The rule
                    </p>
                    <p className='text-sm leading-relaxed text-brand-navy'>
                      {policy.rule_text}
                    </p>
                  </div>
                )}

                <div className='space-y-2'>
                  {policy.parameters.map((param) => (
                    <ParameterField
                      key={param.name}
                      param={param}
                      draft={drafts[param.name] ?? param.value}
                      onChange={(value) =>
                        setDrafts((d) => ({ ...d, [param.name]: value }))
                      }
                    />
                  ))}
                </div>

                {problems.length > 0 && (
                  <div className='rounded-lg border border-red-200 bg-red-50 p-3'>
                    {problems.map((p) => (
                      <p key={p} className='text-xs text-red-700'>
                        {p}
                      </p>
                    ))}
                  </div>
                )}

                {feedback && (
                  <p className='text-xs font-medium text-emerald-700'>{feedback}</p>
                )}

                <div className='flex flex-wrap items-center gap-2'>
                  <Button
                    onClick={save}
                    disabled={!dirty || saving}
                    variant='gradient'
                    size='sm'
                  >
                    {saving ? 'Saving…' : 'Save changes'}
                  </Button>
                  <Button onClick={reset} disabled={saving} variant='outline' size='sm'>
                    Reset to defaults
                  </Button>
                  {policy.updated_by && (
                    <span className='text-xs text-muted-foreground'>
                      Last changed by {policy.updated_by}{' '}
                      {formatRelative(policy.updated_at)}
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [inputs, setInputs] = useState<EffectiveInputs | null>(null)
  const [summary, setSummary] = useState<EvaluationSummary | null>(null)
  const [evaluations, setEvaluations] = useState<PolicyEvaluation[]>([])
  const [changes, setChanges] = useState<PolicyChange[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'policies' | 'evaluations' | 'changes'>('policies')

  const load = useCallback(async () => {
    try {
      const [list, eff, sum, evals, chg] = await Promise.all([
        policiesApi.list(),
        policiesApi.effectiveInputs(),
        policiesApi.evaluationSummary(),
        policiesApi.evaluations(100),
        policiesApi.changes(50),
      ])
      setPolicies(list.policies)
      setInputs(eff)
      setSummary(sum)
      setEvaluations(evals.evaluations)
      setChanges(chg.changes)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load policies.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const blocked =
    (summary?.by_outcome.block ?? 0) + (summary?.by_outcome.escalate ?? 0)

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          AI <span className='text-gradient'>Policies.</span>
        </h1>
        <p className='mt-3 max-w-3xl text-lg font-light text-muted-foreground'>
          The rules the agent must follow. Edit a value here and it is in force
          on the next agent run — no code, no workflow rebuild.
        </p>
        <p className='mt-2 max-w-3xl text-sm text-muted-foreground'>
          Policies are stored and audited in the Command Center. They are
          enforced by the Operators on Supervity Auto, which read these values as
          workflow inputs.
        </p>
      </motion.div>

      {error && (
        <motion.p variants={itemVariants} className='text-sm text-red-600'>
          {error}
        </motion.p>
      )}

      <motion.div
        className='grid grid-cols-2 gap-4 lg:grid-cols-4'
        variants={itemVariants}
      >
        <Metric
          label='Active Policies'
          value={loading ? '…' : String(policies.filter((p) => p.enabled).length)}
          hint={`${policies.length} defined`}
        />
        <Metric
          label='Evaluations Logged'
          value={loading ? '…' : String(summary?.total ?? 0)}
          hint='reported by Operators'
        />
        <Metric
          label='Blocked or Escalated'
          value={loading ? '…' : String(blocked)}
          hint='times a policy stopped the agent'
        />
        <Metric
          label='Last Evaluation'
          value={
            loading
              ? '…'
              : summary?.last_evaluated_at
                ? formatRelative(summary.last_evaluated_at)
                : '—'
          }
          hint={summary?.total ? undefined : 'no evaluations reported yet'}
        />
      </motion.div>

      <motion.div className='flex flex-wrap gap-2' variants={itemVariants}>
        {(
          [
            ['policies', `Policies (${policies.length})`],
            ['evaluations', `Evaluation log (${summary?.total ?? 0})`],
            ['changes', `Change history (${changes.length})`],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              'rounded-full border px-3 py-1.5 text-sm font-medium transition-colors',
              tab === id
                ? 'border-brand-navy bg-brand-navy text-white'
                : 'border-border/60 bg-white/60 text-muted-foreground hover:text-brand-navy'
            )}
          >
            {label}
          </button>
        ))}
      </motion.div>

      {tab === 'policies' && (
        <motion.div className='space-y-4' variants={itemVariants}>
          {loading && policies.length === 0 && (
            <p className='text-sm text-muted-foreground'>Loading policies…</p>
          )}
          {policies.map((policy) => (
            <PolicyPanel key={policy.key} policy={policy} onSaved={load} />
          ))}

          {inputs && (
            <Card className='relative overflow-hidden'>
              <CardWatermark opacity={3} scale={1.1} />
              <CardContent className='relative z-10 p-5'>
                <h2 className='flex items-center gap-2 font-display text-lg font-bold text-brand-navy'>
                  <Icons.zap
                    className='h-5 w-5 text-brand-cornflower'
                    strokeWidth={1.5}
                  />
                  What the agent will receive
                </h2>
                <p className='mt-1 text-sm text-muted-foreground'>
                  These are the current policy values, keyed by the Supervity
                  Auto workflow input each one feeds. This object is what makes
                  an edit above change agent behaviour on the next run.
                </p>
                <pre className='mt-3 max-h-72 overflow-auto rounded-lg border border-border/40 bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700'>
                  {JSON.stringify(inputs.inputs, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </motion.div>
      )}

      {tab === 'evaluations' && (
        <motion.div variants={itemVariants}>
          <Card className='relative overflow-hidden'>
            <CardWatermark opacity={3} scale={1.1} />
            <CardContent className='relative z-10 p-5'>
              <h2 className='font-display text-lg font-bold text-brand-navy'>
                Every policy evaluation
              </h2>
              <p className='mt-1 text-sm text-muted-foreground'>
                Each row is one rule applied to one thing, as reported by an
                Operator on Auto — with the threshold that was in force at the
                time.
              </p>

              {evaluations.length === 0 ? (
                <div className='mt-4 rounded-xl border border-dashed border-border/60 py-10 text-center'>
                  <p className='text-sm font-medium text-brand-navy'>
                    No evaluations reported yet
                  </p>
                  <p className='mx-auto mt-2 max-w-md text-xs text-muted-foreground'>
                    These appear once an Operator emits a{' '}
                    <code className='font-mono'>policy_evaluations</code> array.
                    The update prompt in{' '}
                    <code className='font-mono'>
                      docs/auto-operators/04-updates-to-existing-operators.md
                    </code>{' '}
                    adds that to the Evidence and Policy Operator.
                  </p>
                </div>
              ) : (
                <div className='mt-4 space-y-2'>
                  {evaluations.map((ev) => (
                    <div
                      key={ev.id}
                      className='rounded-lg border border-border/50 bg-white/60 p-3'
                    >
                      <div className='flex flex-wrap items-center gap-2'>
                        <span
                          className={cn(
                            'rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize',
                            outcomeTone(ev.outcome)
                          )}
                        >
                          {ev.outcome || 'unknown'}
                        </span>
                        <span className='text-sm font-medium text-brand-navy'>
                          {ev.policy_name || ev.policy_key || 'Unattributed policy'}
                        </span>
                        {ev.subject_ref && (
                          <span className='font-mono text-xs text-muted-foreground'>
                            {ev.subject_ref}
                          </span>
                        )}
                        <span className='ml-auto text-[11px] text-muted-foreground'>
                          {formatRelative(ev.evaluated_at)}
                        </span>
                      </div>

                      {ev.reason && (
                        <p className='mt-1.5 text-xs text-muted-foreground'>
                          {ev.reason}
                        </p>
                      )}

                      <div className='mt-2 flex flex-wrap gap-3 text-[11px] text-muted-foreground'>
                        {ev.threshold_in_force !== null &&
                          ev.threshold_in_force !== undefined && (
                            <span className='font-mono'>
                              threshold {JSON.stringify(ev.threshold_in_force)}
                            </span>
                          )}
                        {ev.observed_values !== null &&
                          ev.observed_values !== undefined && (
                            <span className='font-mono'>
                              observed {JSON.stringify(ev.observed_values)}
                            </span>
                          )}
                        {ev.workflow_name && <span>{ev.workflow_name}</span>}
                        {ev.step_name && <span>step “{ev.step_name}”</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {tab === 'changes' && (
        <motion.div variants={itemVariants}>
          <Card className='relative overflow-hidden'>
            <CardWatermark opacity={3} scale={1.1} />
            <CardContent className='relative z-10 p-5'>
              <h2 className='font-display text-lg font-bold text-brand-navy'>
                Who changed what
              </h2>
              <p className='mt-1 text-sm text-muted-foreground'>
                Every policy edit, with the value before and after.
              </p>

              {changes.length === 0 ? (
                <p className='mt-4 text-sm text-muted-foreground'>
                  No policy has been changed yet.
                </p>
              ) : (
                <div className='mt-4 space-y-1.5'>
                  {changes.map((change) => (
                    <div
                      key={change.id}
                      className='flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border/50 bg-white/60 px-3 py-2 text-xs'
                    >
                      <span className='font-mono text-brand-navy'>
                        {change.policy_key}
                      </span>
                      <span className='text-muted-foreground'>
                        {change.field.replace('parameters.', '')}
                      </span>
                      <span className='font-mono'>
                        <span className='text-red-500 line-through'>
                          {change.old_value ?? '—'}
                        </span>{' '}
                        <span className='text-emerald-600'>
                          {change.new_value ?? '—'}
                        </span>
                      </span>
                      {change.note && (
                        <span className='text-muted-foreground'>
                          “{change.note}”
                        </span>
                      )}
                      <span className='ml-auto text-muted-foreground'>
                        {change.changed_by} · {formatRelative(change.changed_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </motion.div>
  )
}
