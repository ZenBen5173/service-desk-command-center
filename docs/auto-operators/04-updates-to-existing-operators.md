# Updates to the three untouched Round 1 Operators

These three still run their Round 1 logic. They work, but they miss the Round 2
traps, and you can see it on screen: the Change-Approval form shows
`SLA: N/A (BREACH: NO)` and `AI REC: N/A (N/A CONFIDENCE)` because Triage never
computes a business-hours SLA and Evidence never passes its confidence through.

**Priority order:** Triage first — it fills those blanks and business-hours SLA
is one of the four judged metrics. The other two are polish.

The Human Review Escalation Operator needs nothing.

## How to paste these without losing the work

Three things went wrong today. All three are avoidable:

1. **Check the chat title before pasting.** An Orchestrator prompt went into the
   Correlator's chat once. The title bar is the only reliable signal.
2. **Click "Yes, save the updates" at the end.** Auto describes the change and
   then waits. Twice nothing persisted because that button was never pressed.
3. **Verify the timestamp.** On the Operators page the card should read
   "just now". If it still says days ago, the save did not land — no matter what
   the chat claimed.

Each prompt below ends by asking Auto to read its own configuration back, so you
get a second check for free.

---

## 1. Ticket Queue Triage Operator — do this one

Auto id `019f75d2-b5c9-7000-8efb-17d72d2620a6`

### Paste into that workflow's chat

Update this workflow to handle the Round 2 export. Keep the existing triage
counts and GitHub idempotency exactly as they are — both work. Add the
following.

**New workflow inputs**, all required:

- `onedrive_folder` — the folder holding the CSV exports. Default
  `/Supevity-Hackathon/Round 2/input/`. The root folder is spelled "Supevity"
  without the r, and "Round 2" contains a space. Use it exactly as written.
- `business_hours_only` (boolean, default true)
- `vip_fast_track` (boolean, default true)
- `breach_forecast_hours` (number, default 4)

Read the SLA calendar and the user directory from that same folder, discovering
the files at runtime rather than assuming their names.

**Fix the import.** Before counting anything: drop byte-identical duplicate rows,
then deduplicate by issue key keeping the most recently updated row, and report
how many of each were removed. The export contains genuinely identical repeated
rows and every count is wrong without this.

**Fix date parsing.** The created column mixes four formats. Parse the
unambiguous ones first — ISO datetime, ISO date, and abbreviated month-name
dates — and never reject those. Only the ambiguous slash-format values get a
day-first versus month-first test, decided by which reading puts more values
inside the range the unambiguous dates establish. Report how many parsed under
each format. A silently wrong date is worse than a loud failure.

**Replace elapsed-time SLA with business-hours SLA.** Load the SLA calendar and
compute each ticket's SLA against its region's working hours, holidays and
timezone rather than raw wall-clock time. A ticket raised in the evening does not
burn its clock overnight. Determine the region from the data; if a ticket's
region cannot be resolved, fall back to elapsed time but mark that ticket
`sla_basis = "elapsed_fallback"` so the estimate is never mistaken for an
authoritative one.

Emit per ticket: `sla_state`, `sla_basis`, `business_hours_remaining`,
`forecast_breach_at`, and `breached` as a boolean. Downstream Operators and the
Command Center read these field names, so use them exactly.

**Treat a blank first-response time as a signal.** It means no first response has
happened, which is its own SLA condition and should raise the ticket's priority
rather than being skipped as missing data.

**Add VIP fast-tracking.** Resolve the requester through the user directory by
account identifier only — this dataset contains different people sharing a
display name, so name matching will select the wrong person. If a requester
resolves to zero or more than one account, do not guess: mark the ticket
`identity_unresolved = true` and route it to human review. When the requester is
flagged VIP and `vip_fast_track` is on, raise the ticket's queue position — but
VIP status never bypasses a safety check.

**Order the queue by forecast breach**, not raw age: soonest to breach on the
business-hours clock first, with VIP and no-first-response as tie-breakers.

**Add to the structured output**, keeping every existing field: the duplicate
counts, the date-format counts, the SLA fields above, the identity-unresolved
list, and the ordered queue.

Do not hardcode any ticket key, person, region name or expected count. The judged
dataset has the same schema and different rows.

When you have saved, list this workflow's inputs and its step ids back to me so I
can confirm the change landed.

---

## 2. Ticket Evidence and Policy Operator — optional

Auto id `019f75ad-927c-7000-bb3c-06ff86773d2b`

### Paste into that workflow's chat

Update this workflow to log every policy evaluation and to pass its confidence
through. Keep the existing evidence lookups and the governed decision output.

**New workflow inputs**, all required:

- `change_requests_path` — the change-request export in the same OneDrive folder
- `duplicate_collapse` (boolean, default true)

**Emit the confidence.** Every decision must carry `confidence` as a number, and
the knowledge article match must carry its own `match_confidence`. These
currently arrive empty downstream, which is why the approval form shows
"N/A confidence" and a human cannot see how sure the agent was.

**Log every policy evaluation.** Emit a `policy_evaluations` array where each
entry carries:

- `policy_key` — a stable identifier for the rule, such as
  `auto_remediation_gate`
- `policy_name` — the readable name
- `outcome` — pass, fail, block or escalate
- `reason` — one sentence naming the specific evidence
- `threshold_in_force` — the parameter values in effect at evaluation time
- `observed_values` — what those were compared against

Put these fields at the top level of each entry, not nested inside another
object. Include the array even when everything passes.

**Add a duplicate check.** Find other open tickets from the same requester,
resolved by account identifier only, describing the same problem. Compare on
meaning, not identical text — the same complaint appears in several languages in
this dataset. When duplicates are found and `duplicate_collapse` is on, nominate
the earliest as canonical and mark the rest for linking and closure rather than
remediating each separately.

**Never treat a generically-titled knowledge article as a confident match.** If
an article's title carries no specific meaning, discount its match confidence
rather than accepting it.

**Keep access changes out of automation.** A pending or revoked access record is
evidence against granting access, and missing access evidence is never permission
to grant.

Do not hardcode ticket keys, article identifiers, people, thresholds or expected
counts.

When you have saved, list this workflow's inputs and its step ids back to me.

---

## 3. Safe Resolution and Communication Operator — optional

Auto id `019f758f-a7cd-7000-a985-e4901d30a087`

### Paste into that workflow's chat

Update this workflow to verify its own fixes and reply in the requester's
language. Keep the existing guardrails, idempotency and pending-verification
behaviour.

**New workflow inputs**, all required unless noted:

- `reply_in_requester_language` (boolean, default true)
- `verify_after_remediate` (boolean, default true)
- `incident_parent_ref` (text, optional)

**Reply in the requester's language.** Detect it from the text the requester
actually wrote on the ticket, not from any region or country field. Compose the
reply in that language. If it cannot be determined confidently, use the
organisation default and mark the message `language_fallback = true` rather than
guessing.

**Verify after remediating.** After applying a fix, re-check the ticket's state
rather than assuming success. If the change that delivered the fix was later
rolled back, or the same symptom reappears, do not close it: reopen it, mark it
verification-failed, and emit it as an exception for human review. A fix that did
not hold is worse than no fix, because it hides the problem.

**Respect major incidents.** When `incident_parent_ref` is supplied, this ticket
is one of many sharing a root cause. Do not send an individual message — the
correlator produces one communication for the whole cluster. Link the ticket to
the parent and record that communication was handled at cluster level.

**Never close a ticket whose change control is unresolved.** If a related change
request is awaiting approval or was rolled back, stop and escalate instead.

**Add to the structured output**: the detected language and whether it fell back,
the verification result, whether communication was suppressed as part of a
cluster, and the reason for any escalation.

Do not hardcode ticket keys, recipients, languages or expected counts.

When you have saved, list this workflow's inputs and its step ids back to me.
