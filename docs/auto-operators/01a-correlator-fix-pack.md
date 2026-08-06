# Correlator fix pack — paste into the existing workflow chat

The first run of the Major-Incident Correlator built cleanly and normalised the
data correctly, but its clustering step was badly wrong. Do not rebuild the
workflow. Paste the **Fix prompt** below into the same Auto chat and re-run.

## What the first run got right

Worth keeping — the normalisation is solid and matches the dataset exactly:

- 462 rows read, **2 byte-identical duplicates dropped** — the seeded trap
- **58 status/resolution conflicts** detected and kept actionable
- Blank-field counts correct: 27 blank channel, 58 blank escalation risk,
  143 blank confidence, 191 with no first response

## What went wrong

**1. It ignored the explicit incident links. This is the serious one.**

`Incident_Problem_Links.csv` contains 31 rows that name the parent incident
outright — 23 of them point at a single parent with the relationship
`is caused by`. That is the payroll-portal major incident, handed over for
free, requiring no clustering judgement at all. The run returned
`"major_incidents": []`.

**2. It clustered 13 tickets out of 460.**

Eight clusters covering 13 tickets is 2.8% coverage. The step sampled rather
than covering the actionable set, and reported no warning about it.

**3. Every cluster came back dated `2026-12-07T00:00:00`.**

One identical timestamp across unrelated tickets is not a real date. The actual
data is entirely July 2026, and the day-first slash dates (`15/07/2026`) appear
to have been read month-first. The 30-day lookback then measured from that wrong
date and excluded nearly the whole dataset — which is what caused fault 2.

Note that `unparseable_dates` was reported as zero. Nothing failed loudly; it
silently produced wrong dates, which is worse.

---

## Fix prompt — paste everything below into the Auto chat

The last run had three faults. Fix all three, keep everything else as it is —
the normalisation counts were correct and must not change.

### Fault 1 — explicit incident links were ignored

Before doing any similarity-based clustering, load the incident/problem links
export from the same OneDrive folder and use it as ground truth.

Each row names a child ticket, a parent incident, and the relationship between
them. Any row whose relationship indicates causation groups that child under
that parent. Build those clusters first, directly from the edges, with no
language model involved. A cluster formed from explicit links must be marked
with the evidence `explicit_link` and must never be discarded or overridden by
the similarity step.

Read the column names from the file at runtime rather than assuming them. If the
links export is missing, say so in warnings and continue.

Classify a link-derived cluster as MAJOR_INCIDENT when its member count is at or
above the minimum cluster size and more than one distinct reporter is involved,
using the same rule as every other cluster.

### Fault 2 — only a fraction of tickets were considered

Every actionable ticket must be assigned to exactly one cluster, or explicitly
recorded as unclustered. Do not sample.

If the number of tickets is too large to pass to the language model in one
request, process them in batches and merge the results — do not silently drop
the remainder.

Add these fields to the counts object and fail loudly if they do not reconcile:

- `tickets_considered` — actionable tickets entering the clustering step
- `tickets_clustered` — tickets placed in a cluster
- `tickets_unclustered` — the remainder
- `coverage_pct` — clustered divided by considered

If coverage is below 90%, add a warning saying so explicitly. Silent
under-coverage reads as "there was nothing to find", which is a much worse
failure than reporting a gap.

### Fault 3 — dates were parsed wrongly and the window hid the data

The created-date column mixes four formats in the same column. Two of them are
unambiguous. The slash format is not: `15/07/2026` could be read day-first or
month-first, and reading it wrongly moves the ticket by months.

Resolve it from the data itself, not from an assumption:

1. Parse every unambiguous date first — the ISO datetimes, the ISO dates and the
   abbreviated month-name dates. These establish the real date range of the
   dataset.
2. For the ambiguous slash dates, try both day-first and month-first across the
   whole column. Pick the interpretation under which more values fall inside the
   range established in step 1, and under which no value is impossible.
3. Record the interpretation chosen and the count parsed each way in the output,
   so the decision is visible rather than assumed.

Never let a parsed date land outside the range of the unambiguous dates by more
than a few days. If it does, that value is a parse failure: keep the row, set
the date to null, and list it under `unparseable_dates`.

Then change the window: `lookback_days` must default to `0`, meaning no window
at all — cluster the entire dataset. Only apply a window when the input is
greater than zero. The judged dataset may cover any period, and a window
measured from a mis-parsed date silently discards almost everything.

### What a correct run looks like

- one cluster with roughly two dozen members, built from explicit links,
  classified MAJOR_INCIDENT, spanning four languages
- a second, smaller link-derived cluster
- `coverage_pct` at or near 100
- `tickets_deflected` in the twenties, not zero
- cluster dates spread across the real range, not one repeated timestamp

Re-run with `lookback_days = 0` and `min_cluster_size = 5` after applying this.
