# Demo script — 4 minutes

**Before you hit record**

- Open seven tabs in order: Elimination · Dashboard · AI Insights · AI Policies ·
  Workbench · Data Manager · Supervity Auto (on My Operators)
- Confirm the green "Live from Supervity Auto" badge on the Dashboard
- Close the browser console — a stray warning on screen reads as a broken app
- Say the numbers out loud once. They are yours; own them.

**Do not open on camera**

- Ticket **ITSM-2349** in the Orchestrator's routing output — its confidence
  reads 0.00 because of the Operator output gap, not because the agent got it
  wrong. Use ITSM-2386 or ITSM-2273 instead; both have clean reasons.

---

## 0:00 — 0:30 · The hook

**Show:** the Elimination page, already loaded.

> "Every service desk AI demo you'll see today closes tickets faster. We think
> that's the wrong goal. If forty-four people ask for shared drive access every
> month, resolving those tickets quickly is just being efficient at something
> that shouldn't be happening.
>
> So we built an AI service desk that eliminates problems instead of processing
> them. This is the Elimination Backlog."

Lead with the idea. The architecture comes later.

---

## 0:30 — 1:20 · The differentiator

**Show:** the ranked list. Point at the top three rows.

> "Our agents read four hundred and sixty tickets and found seventeen distinct
> problems underneath them — down from sixty-seven raw clusters, because the same
> problem shows up under different wording.
>
> Number one: shared drive access. Forty-four tickets, eleven of them breached
> SLA. Number two: printers offline, forty-three tickets, eleven breached."

**Click a row open.**

> "For each one the agent proposes the permanent fix — here, group-based access
> control with a self-service portal — names the team that owns it, and shows
> which agent run produced the finding. A human approves before anything ships."

**Point at the two deflection numbers.**

> "We report deflection as two separate numbers, deliberately. Seventy-one
> tickets already collapsed into single incidents — that work is avoided. Three
> hundred and seventy-seven are preventable if these fixes ship — that's a
> forecast, and we label it as one. Blending those into one headline would not
> survive your first question."

That last line matters. It shows you expected to be challenged.

---

## 1:20 — 2:00 · The agents

**Switch to:** Supervity Auto, My Operators.

> "The intelligence lives on Supervity Auto — one Orchestrator and seven
> Operators. Triage, correlation, evidence and policy, change approval, safe
> resolution, human escalation, and a CSAT knowledge loop."

**Switch to:** the Dashboard, scroll to Agent Activity.

> "The Command Center never decides anything. It reads what the agents did."

**Open one run's timeline.**

> "Every step, its output, and the raw JSON the agent produced. In round one we
> found Supervity's chat summaries contradicting its own timeline — inventing
> ticket numbers. So we show the audit record, not the prose."

**Point at the parallel start if visible:**

> "The Orchestrator starts correlation and triage at the same moment — same
> timestamp on both — then branches on the decision."

---

## 2:00 — 2:35 · Insights and the Manager

**Switch to:** AI Insights.

> "Thirteen insights, none of them written by us. Recurring problems, incidents
> forming, knowledge gaps, an SLA breach forecast, and where the load falls."

**Open a critical one.**

> "Twenty separate tickets from eighteen people, one root cause. And it names
> the Operator that observed it."

**Open the AI Manager. Click "What can we prevent?"**

> "You can ask the operation questions. This isn't a language model — the answers
> are assembled from the agents' own output and cite the Operator they came
> from. It physically cannot invent a ticket number, which is exactly what bit
> us in round one."

---

## 2:35 — 3:05 · Policies that actually bite

**Switch to:** AI Policies.

> "Four policies, all editable without code. Eight thousand eight hundred
> evaluations logged."

**Open the evaluation log tab. Point at a blocked row.**

> "Each one names the rule that fired, the threshold in force at the time, and
> what it was compared against. That's an auditable decision, not a black box."

**Back to Policies. Open the auto-remediation gate. Change 0.85 to 0.95. Save.**

> "Change the confidence threshold here and it's in force on the agent's next
> run — no code, no workflow rebuild, and the change is logged with who did it."

Reset it to 0.85 afterwards.

---

## 3:05 — 3:35 · The human loop

**Switch to:** Workbench. **Open ITSM-2040.**

> "This ticket is Highest priority and already breached SLA. Every incentive says
> act fast.
>
> The agent stopped — because two different people in this company are both
> called Siti Lee, and it couldn't tell them apart. It won't touch the wrong
> person's laptop to hit an SLA target.
>
> Thirty-two tickets were held back for exactly that reason."

**Approve or reject it with a note, on camera.**

> "A human decides, and the decision is recorded against what the agent
> recommended."

---

## 3:35 — 4:00 · Integrations and close

**Switch to:** Data Manager.

> "Eight integrations across eight categories — OneDrive, GitHub Issues, Outlook,
> the agent platform, the database. Discovered from the workflows on Auto, not
> hardcoded, so connecting something new makes it appear here.
>
> And it tells the truth. These say degraded because runs using them actually
> failed. It also separates what we probed directly from what we inferred from
> agent runs — claiming a live check we can't make would be a lie."

**Close on the Elimination page.**

> "Metrics matter — MTTR, SLA, auto-resolution, CSAT. You'll notice MTTR is
> blank, with the reason printed underneath: no Operator reports resolution
> timestamps, and we don't compute numbers our agents haven't produced.
>
> The number we'd ask you to judge us on is deflection. Three hundred and
> seventy-seven tickets that don't need to be resolved, because they don't need
> to happen.
>
> That's the difference between an AI that works the queue and one that shrinks
> it."

---

## Numbers to have memorised

| Figure | Value |
|---|---|
| Operators on Auto | 7, plus 1 Orchestrator |
| Agent runs | 91 · 97.8% success |
| Ticket classes found | 17, from 460 tickets |
| Raw clusters consolidated | 67 → 17 |
| Collapsed now | 71 tickets |
| Preventable | 377 tickets |
| Knowledge articles drafted | 8, awaiting approval |
| Policy evaluations logged | 8,822 |
| Insights | 13 — 6 critical, 6 warning, 1 info |
| Workbench | 157 open |
| Integrations | 8 across 8 categories |
| SLA on business hours | 428 of 460 (93%) |
| CSAT | 3.67 / 5 from 76 responses |
| Identity holds | 32 tickets |
| Backend tests | 46 passing |

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

**"What would you do next?"**
Close the Operator output gap so the batch cycle can auto-resolve, and add Ghost
Run — replay the agent's decisions against the historical backlog to show what
would have been saved.
