# Orchestrator update

**Action:** open the **Stalled Ticket Resolver Orchestrator** in Auto
(`019f75d3-b71d-7000-917a-157ebcd43c46`) and paste the Update prompt below into
its chat.

Round 1's Orchestrator handles one ticket per cycle through four Operators. Round
2 needs it to run correlation before triage, to call the new Operators, to branch,
and to report the metrics the judges score on.

Do this **after** the new Operators exist, so the Orchestrator has something to
call.

---

## Update prompt — paste into this workflow's chat

Update this Orchestrator to coordinate seven Operators instead of four, and to
process a batch rather than a single ticket per cycle.

Consider renaming it **Service Desk Orchestrator**, since it now does more than
resolve stalled tickets.

### Add these workflow inputs

Keep the existing ones. Add, all required unless noted:

- `onedrive_folder` — the folder holding the CSV exports, replacing the
  single-file path.
- `max_tickets_per_cycle` (number, default 10) — how many tickets to process in
  one run.
- `min_cluster_size` (number, default 5) — passed through to the correlator.
- `poor_score_threshold` (number, default 2) — passed through to the CSAT loop.
- `block_on_open_cab` (boolean, default true) — passed through to the policy and
  change-control Operators.

Every threshold must be an input. An operator has to be able to change one and
see the agent behave differently on the next run, without touching the workflow.

### New execution order

**Phase 1 — correlate first, in parallel with triage.**

Call the **Major-Incident Correlator Operator** and the **Ticket Queue Triage
Operator** at the same time. They read the same data and neither depends on the
other. Wait for both before continuing.

Correlation must happen before any individual ticket is worked. Otherwise the
agent resolves twenty tickets separately that were one problem.

**Phase 2 — reconcile.**

Merge the two results. Any ticket that the correlator placed inside a major
incident is removed from the individual work queue and handled at cluster level:
one parent incident, one communication, members linked. Record how many tickets
were absorbed this way — that number is the deflection figure and it is the
headline metric.

Tickets the correlator flagged as repeat failures or unresolved identities go
straight to human review. They are not eligible for automation.

Take the top `max_tickets_per_cycle` remaining tickets from the triage queue,
ordered by forecast breach on the business-hours clock.

**Phase 3 — evidence and policy, per ticket, in parallel.**

For each selected ticket, call the **Ticket Evidence and Policy Operator**, then
the **Change-Approval Handler Operator**. Different tickets can run concurrently;
within a ticket these two run in order, because change control can overturn a
policy ALLOW.

The combined decision follows this precedence, highest first:

1. Change control blocks — awaiting approval, no approver, or rolled back.
2. Access change requested — never automated.
3. Confidence below the threshold in force, or the knowledge article is not
   marked safe for automation.
4. Otherwise, allow.

A block at any level wins over an allow below it. Record which level decided.

**Phase 4 — act, branching.**

- **ALLOW** → call the **Safe Resolution and Communication Operator**. Pass the
  parent incident reference when the ticket belongs to a cluster, so it suppresses
  the individual message.
- **HUMAN_REVIEW** → call the **Human Review Escalation Operator** with the full
  evidence attached.
- **BLOCKED** → call the **Change-Approval Handler Operator**'s approval path so
  the item lands in front of a human with the change request attached.

**Phase 5 — learn.**

Call the **CSAT and Knowledge Loop Operator** once per cycle, after the work is
done, so it sees this cycle's outcomes.

### Carry state across the cycle

Maintain one run state object throughout, and pass it between Operators rather
than letting each re-derive it: the normalised ticket table, the cluster
assignments, the decision per ticket with the deciding rule, and the accumulated
policy evaluation log.

Never let an Operator silently re-read and re-normalise the source data with
different results than an earlier step. One normalisation per cycle.

### Report these metrics

Compute all of them from this cycle's actual results. Never carry forward a
previous number, and never produce a figure that cannot be traced to source rows.

- **MTTR** — mean time to resolution on the business-hours clock, for tickets
  resolved this cycle.
- **SLA compliance** — the share of tickets within SLA on the business-hours
  clock, with breached and at-risk counts.
- **Auto-resolution rate** — allowed and resolved without human involvement,
  divided by all tickets processed.
- **CSAT** — average satisfaction excluding non-responses, plus the non-response
  rate reported separately.
- **Deflection** — tickets absorbed into major incidents, plus tickets collapsed
  as duplicates, plus the forecast volume of any knowledge article drafted this
  cycle. This is the number no other team will show. Report the components as
  well as the total, so it can be defended.

### Structured output

Return one JSON object holding: the metrics above, the per-ticket decisions with
their deciding rule, the cluster assignments, the full policy evaluation log, the
exceptions routed to humans, and all warnings.

Print a readable summary too — but state plainly that the JSON is the
authoritative record. Where a natural-language summary and the structured output
ever disagree, the structured output is correct. Never restate a ticket key,
identity or confidence value in the summary that does not appear in the JSON.

### Rules that must hold

- Never invent a ticket key, person, article identifier, confidence value or
  metric. If it cannot be traced to a source row, fail and escalate.
- Never hardcode ticket keys, names, expected counts or predetermined decisions.
- Never use scenario keywords as branch conditions.
- The judged dataset has the same schema and different rows. Everything is
  computed at runtime.
