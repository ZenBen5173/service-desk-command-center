# Demo script — two presenters, 10 minutes

Order follows the guidance from Supervity: services, workbench, policies, what
the AI does that a person cannot, the live demo, then the differentiator last.

**Split**

| Presenter | Parts |
|---|---|
| **Thevesh** | Intro · Workbench · What AI does that humans can't · Secret sauce |
| **Zen Ben** | Services · Policies · Live demo |

You alternate every beat. Whoever is not speaking drives the screen for the
other, so nobody talks while hunting for a tab.

**Before you start**

- Tabs, left to right: Data Manager · Workbench · AI Policies · AI Insights ·
  Auto Resolution · Elimination · Dashboard · Supervity Auto
- Present from **localhost**. No cold start, no URL to leak.
- Close the browser console.
- Have the Orchestrator's input form pre-filled but not submitted.
- Numbers move as agents run. Read what is on screen, not what is here.

**Do not open**

- `.env`, or anything showing the API key.
- Run timelines from 5–6 August — some GitHub links in them point at issues
  that have since been deleted.

---

## INTRO — Thevesh · 45 seconds

**Screen:** Elimination page, loaded, not scrolled.

> "A service desk got forty-four separate requests for access to a shared
> drive. Forty-four tickets. Forty-four conversations. Eleven of them breached
> their SLA.
>
> Every AI service desk you'll see today would close those forty-four faster.
>
> Ours asks a different question: why did forty-four people have to ask?
>
> We built an AI service desk that eliminates problems instead of processing
> them. Four hundred and sixty tickets, fifteen root causes, and four hundred
> and seventeen tickets that never needed to exist.
>
> We'll come back to that. First, how it's built."

Then hand over. Do not explain the page yet — it is the closing beat.

---

## 1 · SERVICES — Zen Ben · 45 seconds

**Screen:** Data Manager.

> "Eight integrations across eight categories, and this page is generated from
> the workflows on Auto rather than hardcoded — connect something new there and
> it appears here.
>
> The data comes from OneDrive. The system of record is GitHub Issues. The
> channel out to people is Outlook. The intelligence is one Orchestrator and
> seven Operators on Supervity Auto. This Command Center is the ninth thing —
> it displays and governs, it doesn't decide."

**Point at a degraded badge.**

> "And it tells the truth. These say degraded because runs using them actually
> failed. It also separates what we probed directly from what we inferred from
> agent runs — the Operators reach OneDrive with their own credentials, so our
> backend has nothing to probe. Claiming a live check we can't make would be a
> lie."

---

## 2 · WORKBENCH — Thevesh · 60 seconds

**Screen:** Workbench, **By Class** tab.

> "This is where the agent stops. Everything here is something it refused to do
> alone, and each item arrives with the evidence that stopped it and what it
> would have done instead.
>
> Thirty-six items, five different kinds of stop — a change awaiting board
> approval, a rollback needing verification, a recurring problem needing a
> permanent fix, a knowledge article the agent drafted, and a plain escalation.
>
> They're grouped by the classes the Operators clustered themselves. Deciding
> one class writes that decision to every item in it."

**Open a class. Point at the proposed fix.**

> "The agent's own proposed permanent fix, the owning team, and how many tickets
> it says are in this class.
>
> This read two hundred and forty-seven items until we noticed the queue was
> counting how many times the agents had run, not how much work was waiting.
> Sixty-eight change approvals standing there for five actual tickets. It's
> thirty-six now, and that's the honest number."

---

## 3 · POLICIES — Zen Ben · 60 seconds

**Screen:** AI Policies.

> "Four policies, all editable here without touching code.
>
> The auto-remediation gate: act only if the knowledge base marks the fix safe
> for automation and confidence clears the threshold. SLA and VIP: measured on
> each region's working calendar, not raw elapsed time. Change control: an open
> change request blocks remediation outright. Identity: if the requester can't
> be resolved to exactly one person, stop."

**Open the evaluation log.**

> "Fifteen thousand two hundred and ninety-four evaluations logged. Each names
> the rule that fired, the threshold in force at that moment, and what it was
> compared against.
>
> That last part matters. Edit a threshold later and it never rewrites history —
> so this is an auditable decision, not a black box. I'll change one in a minute
> and you'll see the agent behave differently."

---

## 4 · WHAT THE AI DOES THAT A PERSON CANNOT — Thevesh · 60 seconds

**Screen:** AI Insights.

> "Four things here that a human service desk genuinely cannot do.
>
> **One.** Read four hundred and sixty tickets written over weeks and find the
> fifteen problems underneath them. A person sees the ticket in front of them,
> not the pattern across a month.
>
> **Two.** This incident — twenty-five tickets, twenty-two people, one root
> cause, reported in four different languages. Nobody spots that across
> languages in a live queue.
>
> **Three.** SLA on five regional calendars with different holidays and working
> hours, recomputed for every ticket.
>
> **Four.** Five policy gates checked on every ticket, every time, at four in
> the morning, with no fatigue and no shortcuts."

**Open one insight.**

> "And each comes with the next action, who owns it, and what it's worth. Where
> the agent proposed the fix we label it as the agent's; where it didn't, we say
> it's standard practice. You should always know which sentences came from the
> machine."

---

## 5 · LIVE DEMO — Zen Ben · 4 to 5 minutes

Four actions. Nothing already toured.

### 5a · Run the agent — 90 seconds

**Screen:** Supervity Auto. Submit the Orchestrator.

> "That's a live cycle starting. While it runs, here's a completed one."

**Switch to Dashboard, open a run timeline. Scroll.**

> "Correlation and triage start at the same moment — same timestamp on both.
> Then reconcile drops any ticket already inside an incident, so we don't work
> the same outage twenty-three times.
>
> Every step shows the JSON the agent actually produced."

**Point at a step's raw output.**

> "In round one, this platform's chat told us things its own audit log
> contradicted — invented ticket numbers. It did it again twice today. So we
> render the audit record, never the prose. That isn't a design preference, it's
> a scar."

### 5b · A policy that bites — 75 seconds

**Screen:** AI Policies → auto-remediation gate. Change 0.85 to 0.50. Save.

> "No code, no redeploy. Logged with who changed it and when."

**Switch to Auto Resolution → Re-decide under current policy.**

> "That asks the same Operator on Auto to rule again, under the threshold now in
> force."

**Wait. Point at a changed verdict.**

> "Different verdict, same agent, same ticket. And both evaluations stay on the
> record, each naming the threshold it was made under."

**Reset to 0.85.**

### 5c · Decide a whole class — 75 seconds

**Screen:** Workbench → By Class → open the largest class.

> "Nine items, one problem. The agent proposes moving off manual drive mapping
> to Group Policy with a self-service portal, and names the team that owns it."

**Choose Approve, type a note, click Apply to all.**

> "Written to every item separately, each recording that it was decided as a
> class. So an auditor sees what I actually saw when I decided — not one row
> standing in for nine."

### 5d · Close the knowledge loop — 60 seconds

**Screen:** Workbench → a drafted knowledge article.

> "Here's the part I'd point you at.
>
> Most of the queue is blocked for one reason: no knowledge article covers the
> problem, so the fix isn't marked safe for automation and the gate refuses.
>
> The agent noticed the gap and wrote the article itself. Then it stopped. It
> will not publish to the knowledge base on its own."

**Approve it.**

> "A person publishes. Next cycle, that class has coverage and can resolve
> automatically. That's the loop: the agent finds what it's missing, writes it,
> and asks."

---

## 6 · SECRET SAUCE — Thevesh · 90 seconds

**Screen:** Elimination.

> "Back to where we started.
>
> Four hundred and sixty tickets. Fifteen root causes. Every ticket accounted
> for — the same problem just arrives under a dozen different wordings.
>
> Ranked by what each one actually costs: volume, breaches, satisfaction damage.
> Number one is shared drive access — forty-four tickets, eleven breached."

**Open a row.**

> "The permanent fix, the owning team, and the run that produced the finding. A
> human approves before anything ships — the agent never pushes a systemic
> change on its own."

**Point at the two deflection numbers.**

> "Two numbers, deliberately never blended. Forty tickets already collapsed into
> single incidents — work avoided today. Four hundred and seventeen preventable
> if these fixes ship — a forecast, and we label it as one. Adding them together
> would make a better headline and a worse answer."

**Close.**

> "One last thing. Our MTTR is blank, on purpose, with the reason printed
> underneath: no Operator reports resolution timestamps, and we don't compute
> numbers our agents haven't produced. A dash is honest. A zero is a claim.
>
> That's the system we'd want running our service desk. Not the one that acts
> fastest — the one that knows when to stop, and tells you when it doesn't know.
>
> And the number we'd ask you to judge us on: four hundred and seventeen tickets
> that don't need resolving, because they don't need to happen."

Stop there. Nothing after it.

---

## Numbers to have memorised

Read what is on screen if it differs — these move as agents run.

| Figure | Value |
|---|---|
| Agents | 1 Orchestrator + 7 Operators |
| Agent runs | 288 · 99.3% success |
| Integrations | 8 across 8 categories |
| Policies | 4 · 15,294 evaluations logged |
| Workbench | 36 open · 22 in classes · 14 individual |
| Ticket classes | 15, covering 460 tickets |
| Deflection | 40 collapsed · 417 preventable |
| Insights | 10 |
| SLA on business hours | 428 of 460 · 93% |
| CSAT | 3.67 from 76 responses |
| Knowledge articles drafted | 8, awaiting approval |
| Backend tests | 46 passing |

## If a judge pushes

**"Is any of this hardcoded to the sample data?"**
No ticket key, person, article id or expected count appears anywhere in the
repo. Classes, fixes and rankings are computed at runtime from whatever data is
present. Field-name aliases are mapped because the agent generates its own key
names, but no value is.

**"How do you know the agent didn't make these numbers up?"**
Every panel renders the structured output from the run and names the run and
step that produced it. Where an input is missing we say so.

**"Does it actually resolve tickets automatically?"**
Yes, and we report the rate honestly. Tickets are decided one at a time by the
evidence Operator; the ones that clear are resolved, commented on in GitHub and
emailed to the requester. Most are blocked for one reason — no auto-safe
knowledge article — which is exactly what the Elimination Backlog ranks and what
those drafted articles fix. Ship them and the rate moves.

**"Why one ticket at a time and not the batch?"**
Because Auto returns zero bytes from a sub-workflow call to its parent. The
Orchestrator never receives per-ticket confidence, so it escalates everything on
a 0.00 that was never produced. Six attempts, five approaches; Supervity's own
chat eventually said its planner summarises instructions rather than writing the
code. So the Command Center calls the same Operators over the same public API,
in the same order, and records what they say. It sequences; it does not decide.

**"Why is MTTR blank?"**
No Operator reports resolution timestamps. We could have inferred one, but then
the Command Center and the agents would disagree about the same number.

**"What's the architecture?"**
`ARCHITECTURE.md` — the system, the agent cycle, how a policy edit reaches the
agent, and the mirrored schema, as diagrams.

**"What would you do next?"**
Close the Operator output gap so the batch cycle can auto-resolve end to end,
and add Ghost Run — replay the agent's decisions against the historical backlog
to show what would have been saved.

## If something breaks live

- **Auto is slow** — skip 5a's live trigger, open a completed run instead.
- **A page is blank** — press Sync from Auto; it repopulates from the mirror.
- **The whole app is down** — the deck, `docs/Service-Desk-Command-Center.pptx`,
  carries every number and both diagrams.
