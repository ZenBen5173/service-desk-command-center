# Operator 6 — Change-Approval Handler

**Action:** create a NEW workflow in Auto.
**Why it matters:** this Operator is the enforcement arm of the change-control
policy, one of the three mandatory AI Policies. It is also what stops the agent
from shipping a systemic change on its own — the governance story the judges are
looking for.

**Integrations used:** OneDrive (read), GitHub (write), human input form.

---

## Build prompt — paste everything below into Auto chat

Build a workflow named **Change-Approval Handler Operator**.

Business functions: IT Service Management, Change Management, Governance.

Purpose: decide whether a proposed fix is allowed to proceed. Block anything that
needs change-advisory-board approval, force re-verification on anything that was
rolled back, and route both to a human with the full evidence attached.

### Workflow inputs

- `onedrive_folder` (text, required) — folder holding the CSV exports. Default value: `/Supevity-Hackathon/Round 2/input/`
  (note the folder is spelled "Supevity" without the r, and "Round 2"
  contains a space — use it exactly as written).
- `github_repo` (text, required) — the `owner/repo` ticket system of record.
- `proposed_action` (text, optional) — a JSON payload from the Orchestrator
  describing the fix being considered: the target issue key, the action class,
  and the confidence. When empty, evaluate every actionable ticket instead of one.
- `block_on_missing_approver` (boolean, required, default true) — whether a change
  request that has no named approver counts as unapproved. Keep this an input so
  it can be demonstrated being changed.

### Environment variables

- `MICROSOFT_ONEDRIVE_TOKEN`
- `GITHUB_TOKEN`

### Step 1 — Load change records and tickets

Download the CSV exports from `onedrive_folder`. Discover which files exist at
runtime. The change-request export and the issues export are both required; if
either is missing, stop and emit a clear error rather than proceeding without it.

Normalise as in the other Operators: drop byte-identical duplicate rows,
deduplicate by key keeping the newest, parse the several different date formats
tolerantly, and never fill a blank with a guessed value.

Build the link between change requests and tickets from the data itself — the
change-request rows carry the ticket they relate to. Do not assume a naming
convention; read the relationship from the columns.

### Step 2 — Determine the change state for each ticket (branching)

For every ticket that has one or more related change requests, derive exactly one
state. Read the status values from the data rather than assuming a fixed
vocabulary; match on meaning, and if a status value is unrecognised, treat it as
`UNKNOWN` and route to human review rather than guessing.

- **BLOCKED_PENDING_CAB** — a related change request is awaiting change-advisory-
  board approval and has not been implemented. No automated remediation may
  proceed. This holds regardless of how confident the proposed fix is.
- **BLOCKED_NO_APPROVER** — a related change request has no named approver and
  `block_on_missing_approver` is true. An unapproved change is not an approved
  change.
- **REOPEN_AND_VERIFY** — a related change request was rolled back. The earlier
  fix did not hold. The ticket must be reopened, marked as requiring verification,
  and must never be auto-closed on this run.
- **CLEARED** — every related change request is implemented and approved. The
  proposed action may proceed, subject to the other policies.
- **NO_CHANGE_LINKED** — no related change request. Change control does not
  apply; pass through untouched.

Record, for every ticket, which rule fired and the exact source rows that caused
it. This evidence is what makes the decision auditable, and the Command Center
displays it.

### Step 3 — Enforce

When `proposed_action` was supplied, return a single verdict for it: `ALLOW`,
`BLOCK`, or `REOPEN_AND_VERIFY`, with the rule that fired and the evidence.

When it was not supplied, return the verdict for every actionable ticket.

For every ticket in BLOCKED_PENDING_CAB or BLOCKED_NO_APPROVER:

- Do not remediate. Do not comment a resolution. Do not close.
- Create or update a single approval request in `github_repo`, searching open and
  closed issues first so that repeated runs do not create duplicates.
- Attach: the ticket, the change request, why it is blocked, who the named
  approver should be if the data identifies one, and what the fix would have been.

For every ticket in REOPEN_AND_VERIFY:

- Reopen the ticket if it is not already open.
- Add a verification-required marker and the rolled-back change reference.
- Emit it as an exception so a human confirms the fix before it can close.

### Step 4 — Human approval gate

Present the blocked items on a human input form. Each row shows the ticket, the
blocking rule, the change request, and the proposed fix. The human chooses
approve, reject, or request more information, and may add a note.

Record the decision, the note, and the identity of the decider. Emit these as
structured output — this is the human-in-the-loop record and it must be visible
in an audit trail afterwards.

Nothing in this step may auto-select a default answer on the human's behalf. An
unanswered item stays pending.

### Step 5 — Structured output

Return one JSON object:

- `verdicts` — every evaluated ticket with its state, the rule that fired, and
  the source evidence
- `blocked` — items blocked from remediation, with their approval-request refs
- `reopened` — items forced back open for verification
- `human_decisions` — approve/reject/more-info with note and decider
- `counts` — how many landed in each state
- `warnings` — unknown status values, missing files, unresolved links

Print a short readable summary too, but the JSON is authoritative.

### Rules that must hold

- A pending change-advisory-board approval outranks confidence. A high-confidence
  fix on a blocked ticket is still blocked.
- Never invent an approver, a change reference or a ticket key. If it is not in
  the data, escalate.
- Never hardcode ticket keys, change numbers, people or expected counts.
- Unrecognised status values go to human review, never to a guessed branch.
- Fail safely and return partial results with warnings rather than crashing.

---

## Test run

Run once with defaults, no `proposed_action`. What good looks like:

- several tickets land in BLOCKED_PENDING_CAB, including at least one that is
  itself a major incident — proof that even the biggest fix needs approval
- at least one ticket lands in REOPEN_AND_VERIFY from a rolled-back change
- the human form appears with real evidence attached, not placeholder text

## After it runs

Tell Claude Code the workflow name. The `blocked` and `reopened` lists feed the
Workbench queue, and `verdicts` feeds the policy evaluation log.
