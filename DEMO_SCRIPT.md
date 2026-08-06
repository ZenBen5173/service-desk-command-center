# Demo script — 7 minutes

The Round 2 brief (`docs/hackathon-brief.md`) asks for **5–10 minutes** showing
the full flow: trigger → Orchestrator → delegation → policies enforced →
exception → human resolves → insights. This script covers all seven beats and
lands around 7:00, leaving room to breathe.

**Slides:** `docs/Service-Desk-Command-Center.pptx`, 11 slides, speaker notes on
every one. Slides 1 to 9 make the argument, 10 hands over to the live app, 11
closes. `docs/demo-deck.html` is the same deck as a browser fallback if
PowerPoint misbehaves on the day.

**Before you hit record**

- Open seven tabs in order: Elimination · Dashboard · AI Insights · AI Policies ·
  Workbench · Data Manager · Supervity Auto (on My Operators)
- Confirm the green "Live from Supervity Auto" badge on the Dashboard
- Close the browser console — a stray warning on screen reads as a broken app
- Record from **localhost**, not the tunnel. Faster, and no URL to leak.
- Say the numbers out loud once. They are yours; own them.

**Do not open on camera**

- Ticket **ITSM-2349** in the Orchestrator's routing output — its confidence
  reads 0.00 because of the Operator output gap, not because the agent got it
  wrong. Use ITSM-2386 or ITSM-2273 instead; both have clean reasons.
- Your `.env`, or anything showing the Supervity API key.

---

## 0:00 — 0:35 · The hook

**Show:** the Elimination page, already loaded.

> "Every service desk AI demo you'll see today closes tickets faster. We think
> that's the wrong goal. If forty-four people ask for shared drive access every
> month, resolving those tickets quickly is just being efficient at something
> that shouldn't be happening.
>
> So we built an AI service desk that eliminates problems instead of processing
> them. This is the Elimination Backlog, and it's the number we'd ask you to
> judge us on."

Lead with the idea. The architecture comes later.

---

## 0:35 — 1:40 · The differentiator

**Show:** the ranked list. Point at the top three rows.

> "Our agents read four hundred and sixty tickets and found fifteen distinct
> problems underneath them. Every ticket is accounted for — the same problem just
> shows up under a dozen different wordings.
>
> Number one: shared drive access. Forty-four tickets, eleven of them breached
> SLA. Number two: printers offline, forty-three tickets, eleven breached."

**Click a row open.**

> "For each one the agent proposes the permanent fix — here, group-based access
> control with a self-service portal — names the team that owns it, and shows
> which agent run produced the finding. A human approves before anything ships;
> the agent never pushes a systemic change on its own."

**Point at the two deflection numbers.**

> "We report deflection as two separate numbers, deliberately. Seventy-five
> tickets already collapsed into single incidents — that work is avoided. Three
> hundred and eighty are preventable if these fixes ship — that's a
> forecast, and we label it as one. Blending those into one headline would not
> survive your first question."

That last line matters. It shows you expected to be challenged.

---

## 1:40 — 2:40 · The agents, and the trigger

**Switch to:** Supervity Auto, My Operators.

> "The intelligence lives on Supervity Auto — one Orchestrator and seven
> Operators. Triage, correlation, evidence and policy, change approval, safe
> resolution, human escalation, and a CSAT knowledge loop. Nothing here is
> reimplemented in our code."

**Switch to:** the Dashboard, scroll to Agent Activity.

> "Ninety-six runs, ninety-eight percent success. The Command Center never
> decides anything — it reads what the agents did."

**Open one Orchestrator run's timeline. Scroll through the steps.**

> "This is one full cycle. It starts with a trigger — the OneDrive folder, the
> GitHub repo, and the policy thresholds currently in force.
>
> Correlation and triage start at the same moment — same timestamp on both.
> Then reconcile drops any ticket already inside an incident, so we don't work
> the same outage twenty-three times."

**Point at a step's raw output.**

> "Every step shows the JSON the agent actually produced. In round one we found
> Supervity's own chat summaries contradicting its timeline — inventing ticket
> numbers that were never in the data. So we show the audit record, never the
> prose."

---

## 2:40 — 3:30 · Policies that actually bite

**Switch to:** AI Policies.

> "Four policies, all editable without code. Nine thousand seven hundred
> evaluations logged."

**Open the evaluation log tab. Point at a blocked row.**

> "Each one names the rule that fired, the threshold that was in force at that
> moment, and what it was compared against. A later edit never rewrites history —
> so this is an auditable decision, not a black box."

**Back to Policies. Open the auto-remediation gate. Change 0.85 to 0.95. Save.**

> "Change the confidence threshold here and it becomes an input on the agent's
> next run. No code, no workflow rebuild, and the change is logged with who did
> it and when."

**Show the change history entry that just appeared.**

> "Four separate reasons this agent will stop, in strict precedence: an open
> change request outranks everything, then an access or entitlement change, then
> unresolved requester identity, then confidence below this gate. None of them
> can be overridden by urgency."

Reset it to 0.85 afterwards.

---

## 3:30 — 4:40 · The human loop

**Switch to:** Workbench.

> "A hundred and seventy-seven items are waiting on a person, and they're not a
> pile of failures — they're four different kinds of stop."

**Open a `change approval` item — ITSM-2211.**

> "This one is blocked pending change-advisory-board approval. The agent had a
> fix. It opened a GitHub issue in the system of record, then stopped, because an
> open change request outranks its own confidence.
>
> Fifty tickets are sitting here for that reason — including the payroll
> outage itself, the biggest incident in the dataset."

**Open a `verification required` item — ITSM-2216.**

> "Twenty-four of these. A change was rolled back, so the agent forced the ticket
> back open and demanded verification rather than trusting the original fix."

**Open one of the repeat-failure items — ITSM-2217.**

> "And this is the interesting class. One person, the same complaint twice. The
> agent's read is that the fix didn't work — so the answer isn't to resolve it
> faster, it's to replace the asset. That's elimination thinking inside a single
> ticket."

**Approve or reject one with a note, on camera.**

> "A human decides, and the decision is recorded against what the agent
> recommended — so you can audit not just what happened, but whether the agent's
> advice was any good."

---

## 4:40 — 5:35 · Insights, and an agent that admits what it doesn't know

**Switch to:** AI Insights.

> "Twelve insights, none of them written by us — recurring problems, incidents
> forming, knowledge gaps, an SLA breach forecast, and where the load falls."

**Open the payroll major-incident card.**

> "Twenty-five tickets from twenty-two people, one root cause — reported in four
> different languages. The clustering that recognised those as the same problem
> ran inside the Correlator on Auto. This page ranks it and names the run."

**Open the SLA breach forecast.**

> "Fifty tickets already breached, measured on each region's real working
> calendar rather than raw elapsed time. Thirty-seven of them never got a first
> response at all — and the agent counts that as a signal, not a blank."

**Open the AI Manager. Click "What can we prevent?"**

> "You can ask the operation questions. The answers are assembled from the
> agents' own output and cite the Operator they came from."

**Type something off-topic — "tell me a joke".**

> "And when it can't answer from agent data, it says so instead of guessing.
> There's no language model behind this — it physically cannot invent a ticket
> number, which is exactly what bit us in round one."

---

## 5:35 — 6:20 · Integrations and honest health

**Switch to:** Data Manager.

> "Eight integrations across eight categories — OneDrive, GitHub Issues, Outlook,
> the agent platform, the database. Discovered from the workflows on Auto, not
> hardcoded, so connecting something new there makes it appear here."

**Point at a degraded badge.**

> "And it tells the truth. These say degraded because runs using them actually
> failed. It also separates what we probed directly from what we inferred from
> agent runs — OneDrive and GitHub are reached by the Operators with their own
> credentials, so our backend has nothing to probe. Claiming a live check we
> can't make would be a lie."

---

## 6:20 — 7:00 · Close

**Back to:** the Dashboard business outcomes.

> "Metrics: SLA compliance measured on each region's real business-hours
> calendar — four hundred and twenty-eight of four hundred and sixty. CSAT three
> point six seven. And you'll notice MTTR is blank, with the reason printed
> underneath: no Operator reports resolution timestamps, and we don't compute
> numbers our agents haven't produced. A dash is honest; a zero is a claim."

**Close on the Elimination page.**

> "Thirty-two tickets were held back today because three employees share a
> display name and the agent wouldn't guess which person it was — even on a
> Highest-priority ticket that had already breached SLA.
>
> That's the system we'd want running our service desk. Not the one that acts
> fastest — the one that knows when to stop.
>
> And the number to judge us on: three hundred and seventy-seven tickets that
> don't need resolving, because they don't need to happen."

---

## Numbers to have memorised

| Figure | Value |
|---|---|
| Operators on Auto | 7, plus 1 Orchestrator |
| Agent runs | 96 · 97.8% success |
| Ticket classes found | 15, covering all 460 tickets |
| Awaiting human approval | 5 classes |
| Collapsed now | 75 tickets |
| Preventable | 380 tickets |
| Knowledge articles drafted | 8, awaiting approval |
| Policy evaluations logged | 9,752 |
| Insights | 12 — 6 critical, 6 warning |
| Workbench | 177 open |
| Integrations | 8 across 8 categories |
| SLA on business hours | 428 of 460 (93%) |
| CSAT | 3.67 / 5 from 76 responses |
| Identity holds | 32 tickets |
| Backend tests | 46 passing |

## Tickets that are safe to open on camera

| Ticket | What it shows |
|---|---|
| ITSM-2211 | Change approval blocked, with a real GitHub issue link |
| ITSM-2216 | Rollback → forced reopen and verification |
| ITSM-2217 | Repeat failure, single reporter — replace the asset |
| ITSM-2386 | Escalated on VIP policy, clean reason |
| ITSM-2273 | Escalated as an access change, clean reason |

**ITSM-2040 is not in the Workbench** — an earlier draft of this script named it.
Use the five above.

## If a judge pushes

**"Is any of this hardcoded to the sample data?"**
No ticket key, person, article id or expected count appears anywhere in the repo.
Classes, fixes and rankings are computed at runtime from whatever data is
present. Field-name aliases are mapped because the agent generates its own key
names, but no value is.

**"How do you know the agent didn't make these numbers up?"**
Every panel renders the structured output from the run and shows which run and
which step produced it. Where an input is missing we say so — the ranking lists
exactly which inputs each class lacked and confirms they contributed nothing.

**"Does it actually resolve tickets automatically?"**
It decides which tickets are safe to resolve automatically — you can see it clear
one at 0.99 confidence against five policy gates. In the batch cycle it escalates
instead, because it can't confirm confidence per ticket, and it won't act without
that. We'd rather it stopped than guessed.

**"Why is MTTR blank?"**
Because no Operator reports resolution timestamps yet. We could have inferred one
here, but then the Command Center and the agents would disagree about the same
number. A dash is honest.

**"What's the architecture?"**
`ARCHITECTURE.md` in the repo — the system, the agent cycle, how a policy edit
reaches the agent, and the mirrored schema, as diagrams.

**"What would you do next?"**
Close the Operator output gap so the batch cycle can auto-resolve end to end, and
add Ghost Run — replay the agent's decisions against the historical backlog to
show what would have been saved.
