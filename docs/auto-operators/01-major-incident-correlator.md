# Operator 5 — Major-Incident Correlator

**Action:** create a NEW workflow in Auto.
**Why it matters:** this is the moment where dozens of tickets collapse into one
incident with one comms thread instead of dozens of duplicate replies. It also
takes you from 4 Operators to 5, which is an elimination rule.

**Integrations used:** OneDrive (read), GitHub (write), LLM (clustering).

---

## Build prompt — paste everything below into Auto chat

Build a workflow named **Major-Incident Correlator Operator**.

Business functions: IT Service Management, Incident Management, Support Engineering.

Purpose: detect when many separate tickets share one underlying root cause, group
them into a single incident, and make sure the organisation responds once rather
than once per ticket.

### Workflow inputs

- `onedrive_folder` (text, required) — the OneDrive folder holding the CSV
  exports. Default value: `/Supevity-Hackathon/Round 2/input/`
  (note the folder is spelled "Supevity" without the r, and "Round 2"
  contains a space — use it exactly as written).
- `github_repo` (text, required) — the `owner/repo` ticket system of record.
- `min_cluster_size` (number, required, default 5) — the smallest number of
  related tickets that counts as a major incident. This must stay an input so an
  operator can tune it without editing the workflow.
- `lookback_days` (number, required, default 0) — how far back to cluster. Zero
  means no window at all: cluster the entire dataset. Only apply a window when
  this is greater than zero. A window measured from a mis-parsed date silently
  discards almost the whole dataset, which looks like "nothing to find".

### Environment variables

- `MICROSOFT_ONEDRIVE_TOKEN`
- `GITHUB_TOKEN`

### Step 1 — Load and normalise

Download every CSV in `onedrive_folder` using the Microsoft Graph API with
`MICROSOFT_ONEDRIVE_TOKEN`. Load them with pandas. Discover the files present at
runtime; do not assume a fixed file list beyond the issues export being required.

Normalise before anything else:

- Drop byte-identical duplicate rows, then deduplicate by issue key, keeping the
  most recently updated row. Report how many were removed.
- Parse the created and updated timestamps tolerantly. The export mixes four
  date formats in the same column. Two are unambiguous; the slash format is not
  — `15/07/2026` can be read day-first or month-first, and reading it wrongly
  moves the ticket by months. Resolve it from the data, not from an assumption:
  parse every unambiguous value first to establish the dataset's real date
  range, then try the slash dates both ways across the whole column and keep the
  interpretation under which more values fall inside that range and none is
  impossible. Record which interpretation won, and how many parsed each way.
  Any value landing far outside the established range is a parse failure: keep
  the row, set the date to null, and list it under `unparseable_dates`. Never
  guess a date, and never let a wrong date pass silently — a silently wrong date
  is worse than a loud failure.
- Treat blank fields as signals. Record counts of blanks per column rather than
  filling them in.
- Compute a `canonical_resolved` flag: true only when the status indicates
  resolution AND the resolution field indicates completion. When exactly one of
  the two indicates resolution, mark the row `state_conflict = true`. State
  conflicts stay in the actionable pool.

Output the normalised ticket table plus a counts object: total rows read, exact
duplicates dropped, key duplicates dropped, canonical resolved, state conflicts,
actionable, unparseable dates, and the slash-date interpretation chosen.

### Step 2 — Build correlation candidates

Restrict to tickets created within `lookback_days` of the most recent created
date found in the data. Derive the window from the data itself — never from
today's real-world date, because the judged dataset may cover a different period.

Group tickets into candidate clusters using all of these signals together:

1. **Explicit links — do this first, before any language model runs.** The
   incident/problem link export names child tickets, their parent incident, and
   the relationship between them. Any row whose relationship indicates causation
   groups that child under that parent, directly from the edges, with no
   similarity judgement involved. Mark those clusters with the evidence
   `explicit_link`. They are ground truth and must never be discarded or
   overridden by the similarity step. Read the column names at runtime rather
   than assuming them; if the export is missing, say so in warnings and
   continue.
2. **Semantic similarity of the symptom.** Use the LLM to cluster the summary and
   description text by the underlying problem being reported, not by shared
   keywords. The same complaint may be written in different languages within one
   cluster — the clustering must survive that. Do not translate-and-match on
   fixed phrases; compare meaning.
3. **Affected system.** Infer the affected system from the description text. Be
   explicit that `customfield_10101` is the assignment group and must NOT be used
   as the affected system.
4. **Time proximity**, as a weak supporting signal only. A genuine root cause can
   produce tickets over days, so time must never be the sole grouping rule.

Every actionable ticket must end up in exactly one cluster or be explicitly
recorded as unclustered. Do not sample. If there are too many tickets to pass to
the language model at once, process them in batches and merge — never silently
drop the remainder.

Report `tickets_considered`, `tickets_clustered`, `tickets_unclustered` and
`coverage_pct` in the counts, and add a warning when coverage falls below 90%.
Silent under-coverage reads as "there was nothing to find", which is a far worse
failure than an honest gap.

For each candidate cluster produce: a stable cluster key, the member issue keys,
the member count, the distinct reporter count, the earliest and latest created
timestamps, the languages observed, the breached/at-risk counts, and the
evidence that formed it.

### Step 3 — Classify each cluster (branching)

For every cluster, decide exactly one classification and record the evidence:

- **MAJOR_INCIDENT** — member count is at or above `min_cluster_size` AND the
  distinct reporter count is greater than one. Many people, one symptom.
- **REPEAT_FAILURE** — the cluster is dominated by a single reporter raising the
  same symptom repeatedly. This means an earlier fix did not hold. Do not treat
  it as a major incident; the correct response is asset replacement or a deeper
  fix, and it must be flagged for human review.
- **DUPLICATE_BURST** — a small number of near-identical tickets from the same
  reporter within a short window. Collapse to the earliest and link the rest.
- **BELOW_THRESHOLD** — everything else. Leave alone.

Identity for the reporter comparison must use the account identifier only. This
dataset contains different people who share a display name. If a reporter cannot
be resolved to exactly one account, do not guess — mark the cluster
`identity_unresolved = true` and route it to human review instead of acting.

### Step 4 — Act, once per cluster (branch on classification)

Only clusters classified MAJOR_INCIDENT proceed to action. For each one:

- Search `github_repo` for an existing incident issue for this cluster key,
  checking both open and closed issues, so a re-run does not create a second
  one. Idempotency is mandatory — this workflow will be run repeatedly during a
  demo.
- If none exists, create one parent incident issue containing: the cluster key,
  the inferred root-cause statement, the full member list, the member count, the
  distinct reporter count, the breach count, the languages observed, and the
  first and last observed timestamps.
- If one exists, update it with any new members rather than creating another.
- Link every member ticket to the parent. Do not close member tickets — closure
  is the resolution Operator's job and depends on the fix actually working.
- Produce exactly one communication payload for the whole cluster, containing the
  affected-user list and a single status message. Emit it as structured output
  for the Orchestrator to hand to the communication Operator. Never emit one
  message per member ticket.

Clusters classified REPEAT_FAILURE or `identity_unresolved` must be emitted as
exceptions for human review, with their full evidence attached, and must not
trigger any automated action.

### Step 5 — Structured output

Return a single JSON object. This is read directly by a Command Center, so the
shape matters more than the prose:

- `counts` — the normalisation counts from step 1
- `clusters` — every cluster with its key, classification, members, member count,
  distinct reporters, breach count, languages, and evidence
- `major_incidents` — the parent issue references created or updated
- `deflection` — for each major incident, the member count minus one. That is the
  number of separate handling efforts avoided by collapsing the cluster. Sum
  these into a `tickets_deflected` total.
- `exceptions` — clusters routed to human review, with the reason
- `warnings` — unparseable dates, unresolved identities, missing files

Also print a short human-readable summary, but the JSON object is the
authoritative result. Where the two ever disagree, the JSON is correct.

### Rules that must hold

- Never invent an issue key, a person, a system name or a confidence value. If it
  cannot be traced to a source row, fail the step and escalate.
- Never hardcode any ticket key, reporter name, incident number or expected
  count. The judged dataset has the same schema and different rows.
- Never use scenario keywords as branch conditions. Compute from the data.
- Fail safely: if a download or parse fails, emit the error in `warnings` and
  return partial results rather than crashing.

---

## Test run

Run once with defaults after saving. What good looks like:

- `counts.exact_duplicates_dropped` is greater than zero — the export really does
  contain identical rows
- at least one cluster classified MAJOR_INCIDENT, spanning multiple languages
- at least one cluster classified REPEAT_FAILURE from a single reporter
- `tickets_deflected` is a non-zero number

If it returns zero clusters, lower `min_cluster_size` and re-run — do not edit
the workflow logic to force a result.

## After it runs

Tell Claude Code the workflow name so the Command Center can read its runs. The
`deflection` block feeds the Elimination Backlog panel directly.
