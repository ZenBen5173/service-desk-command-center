# Operator 7 — CSAT & Knowledge Loop

**Action:** create a NEW workflow in Auto.
**Why it matters:** this is the self-learning story. It closes the loop from a bad
satisfaction score back to a knowledge-gap fix, and it produces the knowledge
articles that make whole classes of ticket stop arriving. CSAT is one of the four
judged metrics.

**Integrations used:** OneDrive (read), GitHub (write), Outlook (send), LLM.

---

## Build prompt — paste everything below into Auto chat

Build a workflow named **CSAT and Knowledge Loop Operator**.

Business functions: IT Service Management, Customer Support, Knowledge Management.

Purpose: measure satisfaction honestly, chase the worst-scoring ticket classes,
and turn a repeated unanswered problem into a written knowledge article so it
stops being asked.

### Workflow inputs

- `onedrive_folder` (text, required) — folder holding the CSV exports. Default value: `/Supevity-Hackathon/Round 2/input/`
  (note the folder is spelled "Supevity" without the r, and "Round 2"
  contains a space — use it exactly as written).
- `github_repo` (text, required) — the `owner/repo` ticket system of record.
- `poor_score_threshold` (number, required, default 2) — a satisfaction score at
  or below this triggers a follow-up. Must stay an input.
- `knowledge_gap_min_tickets` (number, required, default 5) — how many tickets of
  one class with no matching knowledge article before an article is drafted.

### Environment variables

- `MICROSOFT_ONEDRIVE_TOKEN`
- `GITHUB_TOKEN`
- `MICROSOFT_OUTLOOK_TOKEN`

### Step 1 — Load and join

Download the CSV exports from `onedrive_folder`. The issues, satisfaction-survey
and knowledge-base exports are all required here; the users export is needed to
resolve requesters. Discover what is present at runtime and emit a clear error
for anything required and missing.

Normalise as in the other Operators: drop byte-identical duplicate rows,
deduplicate by key keeping the newest, parse the several date formats tolerantly,
never fill blanks with guesses.

Join surveys to tickets by the ticket key carried on the survey rows. Join
requesters by account identifier only — display names repeat in this dataset and
name matching will produce wrong people. If a requester resolves to zero or more
than one account, do not act on that row; add it to warnings.

Blank satisfaction scores are non-responses, not zeros. Count them separately and
exclude them from averages. A non-response rate is itself worth reporting.

### Step 2 — Score by ticket class, not by ticket (stateful aggregation)

Group tickets into classes by the underlying problem being reported. Use the LLM
to cluster on meaning, so the same problem written in different words or
different languages lands in the same class. Do not cluster on fixed keywords.

For each class compute, entirely from the data:

- ticket volume
- average satisfaction score, excluding non-responses
- the count of scores at or below `poor_score_threshold`
- the non-response count
- the breach count
- the number of distinct requesters
- whether any knowledge article matches this class

Rank the classes by damage: volume weighted by breaches and by poor scores. The
worst class by satisfaction is rarely the biggest by volume — surface both.

### Step 3 — Branch on what each class needs

Assign each class exactly one treatment and record the evidence:

- **KNOWLEDGE_GAP** — the class has at least `knowledge_gap_min_tickets` tickets
  and no matching knowledge article. Draft one.
- **ARTICLE_INEFFECTIVE** — an article exists but the class still has poor
  satisfaction. The article is wrong or unfindable. Flag it for rewrite with the
  evidence, and do not silently trust it for auto-remediation.
- **FOLLOW_UP_REQUIRED** — individual tickets scored at or below the threshold.
  Chase the requester.
- **HEALTHY** — everything else. No action.

Be explicit that a generically-titled knowledge article must not be treated as a
confident match. If the article title carries no specific meaning, treat the class
as a knowledge gap rather than as covered.

### Step 4 — Act (parallel branches)

For classes marked KNOWLEDGE_GAP, draft a knowledge article containing: the
symptom as users actually describe it, the observed root cause where the data
supports one, the resolution steps taken on tickets in this class that ended
well, and the owning team taken from the assignment group. Mark every draft as
requiring human approval before publication, and mark it as not safe for
auto-remediation until a human says otherwise. The agent never publishes an
article on its own authority.

Search `github_repo` for an existing draft for this class, open and closed, before
creating one. Repeated runs must not create duplicates.

For tickets marked FOLLOW_UP_REQUIRED, draft one Outlook message per affected
requester, in the language the requester used on their ticket. Detect the language
from the ticket text rather than from any country or region field. Each message
acknowledges the poor experience, states what is being done, and asks one specific
question. Draft only — sending to a real person is a human decision, so emit the
drafts as output for approval rather than sending them automatically.

For classes marked ARTICLE_INEFFECTIVE, raise a rewrite request against the
existing article with the evidence attached.

### Step 5 — Structured output

Return one JSON object:

- `classes` — every class with volume, average score, poor-score count,
  non-response count, breach count, distinct requesters, article match, treatment
  and rank
- `csat` — overall average excluding non-responses, the non-response rate, and the
  score distribution
- `drafted_articles` — the article drafts with their target class and evidence
- `follow_ups` — the drafted messages with recipient account identifier and
  language
- `rewrite_requests` — ineffective articles with evidence
- `deflection_forecast` — for each drafted article, the number of tickets in that
  class over the period. That is the volume the article is aimed at preventing.
- `warnings` — unresolved identities, missing files, unparseable dates

Print a short readable summary too. The JSON is authoritative.

### Rules that must hold

- Never invent a satisfaction score, a requester, an article identifier or a root
  cause. Absent evidence, escalate.
- Never hardcode ticket keys, class names, people or expected counts. The judged
  dataset has the same schema and different rows.
- Blank scores are non-responses and must never be averaged as zero.
- Nothing is published or sent without human approval.
- Fail safely; return partial results with warnings.

---

## Test run

Run once with defaults. What good looks like:

- the worst class by average satisfaction is clearly worse than the rest
- a meaningful number of non-responses reported separately from low scores
- at least one knowledge article drafted, with a non-zero deflection forecast
- follow-up drafts appear in more than one language

## After it runs

Tell Claude Code the workflow name. `classes` and `deflection_forecast` feed the
Elimination Backlog panel; `csat` feeds the dashboard metric.
