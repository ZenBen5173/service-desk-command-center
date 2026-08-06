# Fix pack 2 — Correlator and Change-Approval Handler

Both Operators now run end to end against the real dataset. This pack fixes what
the Command Center exposed once their output was actually read.

Paste each **Fix prompt** into that workflow's existing Auto chat. Do not
rebuild either workflow.

---

## A. Major-Incident Correlator

### What it got right on the second run

- 100% coverage — all 460 actionable tickets clustered, none dropped
- The explicit incident links worked: the 23-ticket payroll cluster and the
  7-ticket SSO cluster both found deterministically, marked `explicit_link`
- Three repeat-failure clusters correctly held back for human review
- Ranked classes match the dataset: password reset 29 tickets / 10 breached is
  genuinely the worst class

### What is still wrong

**1. Deflection of 343 is not defensible.**

343 of 465 tickets is 74%. The formula sums `member_count - 1` across every
cluster labelled MAJOR_INCIDENT — but 32 clusters were labelled that way,
including "password reset request" and "keyboard replacement request". Those are
not incidents. Nobody deflects 29 password resets by opening one parent ticket.

**2. One real problem is split across several clusters.**

`guest_wifi_connectivity` and `guest_wifi_connectivity_issue` are the same
thing. So are five separate printer-offline clusters, five monitor-flickering
clusters, and four keyboard clusters. That inflates the class count and hides
the true size of each problem.

**3. Date parsing over-corrected.**

137 values are now unparseable, including plain ISO dates like `2026-07-18` that
have nothing ambiguous about them. Most clusters report `NaT` for their date
range. The previous run parsed everything and got it silently wrong; this one
rejects valid input. Neither is right.

**4. Language detection reports everything as English.**

The payroll cluster contains Spanish, Chinese and French tickets. All were
grouped correctly, which is the hard part — but `languages` says `["en"]`.

### Fix prompt — paste into the Correlator chat

Four corrections. Keep the explicit-link handling and the 100% coverage exactly
as they are; both are working.

**1. Split the classification, and fix deflection.**

`MAJOR_INCIDENT` currently covers two very different things. Separate them:

- **MAJOR_INCIDENT** — a burst sharing one root cause: at or above the minimum
  cluster size, more than one reporter, AND either formed from an explicit
  incident link or spanning a short window relative to the dataset's overall
  span. These genuinely collapse into one parent incident.
- **RECURRING_CLASS** — steady volume of the same request or symptom spread
  across the whole period, from many reporters. These are not incidents. They
  are candidates for permanent elimination: a knowledge article, a self-service
  fix, or an automation. Most of what is currently labelled MAJOR_INCIDENT
  belongs here.

Derive the distinction from the data — compare each cluster's time span against
the dataset's full span — not from the words in the summary.

Then compute deflection separately for each, and never sum them into one
headline number without saying which is which:

- `incident_collapse` — for MAJOR_INCIDENT clusters only, the sum of
  `member_count - 1`. These are handling efforts genuinely avoided right now.
- `elimination_forecast` — for RECURRING_CLASS clusters, the volume the proposed
  permanent fix would prevent going forward. This is a forecast and must be
  labelled as one.

Report both, each with the method used, and state the population each is a share
of. A single blended percentage is not defensible.

**2. Merge clusters that describe the same problem.**

After clustering, run a consolidation pass. Two clusters merge when they concern
the same affected system and the same underlying symptom, even where their
generated keys differ. Compare meaning, not key strings.

Report `clusters_before_merge` and `clusters_after_merge` so the consolidation
is visible. Prefer merging: a split class understates the real cost of the
problem, which is the entire point of ranking them.

**3. Repair date parsing.**

The over-rejection came from applying the outlier test to every value instead of
only to the ambiguous ones. Correct order:

1. Parse the unambiguous formats — ISO datetime, ISO date, and abbreviated
   month-name dates. **These are never rejected.** They define the dataset's
   real date range.
2. Only the ambiguous slash-format values get the day-first versus month-first
   test, and only those may be rejected as unparseable.
3. Report how many values were parsed by each format, so a future regression is
   visible in the counts rather than silent.

No cluster should report a null date range when its members have valid dates.

**4. Detect language from the ticket text.**

Determine each ticket's language from the words the requester actually wrote —
the summary and description — not from any region, country or channel field. A
cluster's `languages` must list every distinct language among its members.

Getting this visible matters: the payroll cluster grouping four languages under
one root cause is the clearest evidence that clustering works on meaning rather
than on keywords.

### Re-run with

`lookback_days = 0`, `min_cluster_size = 5`.

Expect: fewer, larger classes; a small number of true MAJOR_INCIDENTs; the
payroll cluster showing four languages; and two separate, clearly labelled
deflection figures instead of one inflated 343.

---

## B. Change-Approval Handler

### What it got right

- 460 tickets evaluated, 5 blocked pending approval — including the payroll
  major incident, which is exactly the governance story worth showing
- 3 rolled-back changes correctly forced to reopen-and-verify
- 2 human overrides recorded through the approval form
- Unrecognised states routed to review rather than guessed at

### What is still wrong

**1. Verdicts do not name the policy they came from.**

920 evaluations were logged, and every one is unattributed. The Command Center
can show them but cannot say which rule fired, which is most of their value.

**2. Blocked items reach the Workbench with almost no context.**

Each blocked item carries only an issue key, a GitHub URL and a status. A human
reviewing it cannot see the ticket summary, the blocking rule, the change
request, or what the fix would have been — they would have to go and look it up,
which defeats the point of the queue.

**3. The reopen step could not find its tickets.**

Three verification reopens failed with "could not find matching GitHub issue".
The tickets exist in the dataset but not yet as issues in the repository.

### Fix prompt — paste into the Change-Approval Handler chat

Three corrections. Keep the state machine and the human approval gate as they
are; both work.

**1. Name the policy on every verdict.**

Every entry in the verdicts array must carry:

- `policy_key` — a stable identifier for the rule that fired. Use
  `change_control` for change-approval blocks and reopen-and-verify outcomes.
- `policy_name` — the readable name of that rule.
- `reason` — one sentence on why this rule produced this outcome for this
  ticket, naming the specific evidence.
- `threshold_in_force` — the parameter values that were in effect, such as
  whether blocking on a missing approver was enabled.
- `observed_values` — what those were compared against, such as the change
  request status and whether an approver was named.

An evaluation that does not say which rule it came from cannot be audited, and
an unauditable decision is not a governed one.

**2. Give every blocked and reopened item its full context.**

Each item routed to a human must carry enough to decide without leaving the
page:

- the ticket key, its summary, and its priority
- the requester, resolved by account identifier
- the blocking rule and a plain-language reason
- the related change request: its identifier, status, and named approver if any
- `agent_recommendation` — what the agent would have done had it been allowed
- `confidence` where the ticket carries one
- the SLA state and whether it has already breached

**3. Do not fail when a ticket has no matching issue yet.**

When a reopen target does not exist in the repository, create it rather than
warning and moving on — the reopen-and-verify requirement is that the ticket
comes back for verification, and a warning in a log does not achieve that.

If creation is not possible, emit the item as an exception needing human action
rather than only a warning, so it lands in the Workbench instead of being lost.

### Re-run with

The same inputs, `proposed_action` left empty.

Expect: every verdict naming `change_control`, blocked items arriving with the
ticket summary and change request attached, and no "could not find matching
issue" warnings.
