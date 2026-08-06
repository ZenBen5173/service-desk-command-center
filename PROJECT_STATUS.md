# Round 2 — where we stand

Service Desk Command Center · Autopilot Asia 2026 · Track 3, Customer Support
Last updated: 6 Aug 2026

**Live demo** · https://autopilot-frontend-mafd.onrender.com
**Repository** · https://github.com/ZenBen5173/service-desk-command-center
**Architecture** · `ARCHITECTURE.md` · **Demo script** · `DEMO_SCRIPT.md`

> **Where we are:** the application is built, deployed and running on live agent
> data. All five mandatories are met and four of five deliverables are done. What
> is left is recording the demo and posting it.
>
> The free hosting tier idles after 15 minutes, so the first visit takes about a
> minute to wake. Open the link a few minutes before showing it to anyone.

---

## The one-line pitch

Everyone else closes tickets faster. We make classes of ticket stop existing —
and we report the number.

---

## All five mandatories are met

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Orchestrator + ≥5 Operators on Auto | ✅ | **7 Operators + 1 Orchestrator**, parallel start, three-way branch, human gates |
| 2 | Command Center on live agent data | ✅ | 96 real runs, 97.8% success — no template demo data left anywhere |
| 3 | ≥3 editable policies, every evaluation logged | ✅ | **4 policies · 9,752 evaluations**, each naming the rule, the threshold in force and what it was compared against |
| 4 | Live exception resolved in the Workbench | ✅ | **176 open** across 4 stop reasons, each with the evidence that stopped the agent. ITSM-2212 resolved on the deployed instance: the block was upheld because the change request is still open with CAB, with the reason on the record |
| 5 | ≥3 integrations across 2 categories | ✅ | **8 integrations across 8 categories**, discovered from Auto rather than declared |

## The five deliverables

`docs/hackathon-brief.md` asks for five things, not just the mandatories:

| # | Deliverable | Status |
|---|---|---|
| 1 | Working application | ✅ https://autopilot-frontend-mafd.onrender.com |
| 2 | Orchestrator + ≥5 Operators on Auto | ✅ 7 Operators; definitions exported to `docs/auto-workflows/` |
| 3 | Live demo, 5–10 min | ⬜ not recorded — script in `DEMO_SCRIPT.md` runs 7. Likely presented on site; record it anyway for the LinkedIn post and as a fallback |
| 4 | Code repository, clean and documented | ✅ https://github.com/ZenBen5173/service-desk-command-center |
| 5 | Architecture diagram | ✅ `ARCHITECTURE.md` — four diagrams |

## Every component the brief asks for is built

The problem statement lists six things to build, not just the five mandatories:

| Component | Status |
|---|---|
| Command Center | ✅ Live KPIs, agent roster, run timeline with the authoritative JSON |
| AI Policies | ✅ 4 editable rules, full change history and evaluation log |
| AI Insights | ✅ 12 real insights — clusters, incidents, gaps, SLA forecast |
| AI Manager | ✅ Chat answering from mirrored agent data, every answer cited |
| Data Manager | ✅ 8 integrations, health probed or inferred and labelled as which |
| Workbench | ✅ Exceptions with full context, approve / reject / modify / more info |

---

## What runs where

The hard rule: the Orchestrator and every Operator live on Supervity Auto. This
repo never reimplements agent logic — it displays, governs and audits.

| Layer | Where |
|---|---|
| Orchestrator + 7 Operators | Supervity Auto |
| Command Center, Policies, Insights, Manager, Data Manager, Workbench | This repo |
| Source data | OneDrive — `/Supevity-Hackathon/Round 2/input/` |
| Ticket system of record | GitHub Issues |
| Channel | Microsoft Outlook |

## The agents

| Role | Agent | What it does |
|---|---|---|
| Orchestrator | Service Desk Orchestrator | Runs the cycle, delegates to all seven, enforces decision precedence |
| Operator | Ticket Queue Triage | Business-hours SLA per region, VIP fast-track, breach-first ordering |
| Operator | Major-Incident Correlator | Groups tickets by root cause, separates bursts from recurring classes |
| Operator | Ticket Evidence and Policy | Evidence lookups, applies the gates, logs every evaluation |
| Operator | Change-Approval Handler | Blocks fixes awaiting approval, forces reopen after a rollback |
| Operator | Safe Resolution and Communication | Applies the fix, replies in the requester's language, verifies |
| Operator | Human Review Escalation | Packages evidence and hands it to a person |
| Operator | CSAT and Knowledge Loop | Scores satisfaction by class, drafts knowledge articles |

**Cycle shape:** Correlator and Triage start in parallel → reconcile → evidence
and change control per ticket → three-way branch → metrics. Human approval gates
inside the change-control and escalation branches.

---

## Our differentiator: Problem Elimination

The Elimination Backlog ranks *classes* of ticket by what they cost, and shows
the permanent fix an Operator proposed for each.

**15 distinct problems covering all 460 actionable tickets**, five of them
already awaiting human approval:

| Rank | Problem | Tickets | Breached |
|---|---|---|---|
| 1 | Shared-drive access and permissions | 44 | 11 |
| 2 | Network printers offline | 43 | 11 |
| 3 | Mailbox storage limits | 43 | 7 |
| 4 | Guest wifi connectivity | 40 | 10 |
| 5 | Software installation requests | 40 | 7 |
| 6 | Password resets | 37 | 11 |

Each carries a proposed permanent fix — group-based access control with a
self-service portal, static DHCP reservations for printers, automated mailbox
archiving — plus the owning team.

**Deflection is reported as two separate numbers, never blended:**

- **Collapsed now — 75 tickets** — shared one root cause, became a single
  incident with one response. Already avoided.
- **Preventable — 380 tickets** — targeted by the proposed permanent fixes.
  A forecast, conditional on a human approving each one.

Blending those into one headline would not survive a judge's first question.

---

## The judged metrics

| Metric | Value | Source |
|---|---|---|
| CSAT | 3.67 / 5 · 76 responses · 16.5% response rate | CSAT and Knowledge Loop |
| SLA on business hours | 428 of 460 (93%) | Ticket Queue Triage |
| Auto-resolution | 60% — 3 allowed, 2 to review, from single-ticket runs | Evidence and Policy |
| MTTR | **not shown, by choice** | — |
| Deflection | 75 collapsed · 380 preventable | Major-Incident Correlator |

MTTR is deliberately absent with the reason printed on the dashboard: no
Operator reports resolution timestamps, and this repo does not compute metrics
the agents have not produced. A dash is honest; a zero is a claim.

---

## What the agents proved on the real data

Every seeded trap was handled:

- **2 byte-identical duplicate rows** dropped on import
- **58 status/resolution conflicts** detected and kept actionable
- **4 date formats** in one column, with the ambiguous day-first slash dates
  disambiguated from the data rather than assumed
- **23-ticket payroll outage** collapsed into one parent incident, found through
  the explicit incident links rather than guessed
- **7-ticket SSO loop** likewise
- **32 tickets with ambiguous reporter identity** held back — three employees
  share a display name, and the agent refuses to guess which person it is
- **5 tickets blocked** pending change-advisory-board approval, including the
  payroll major incident itself
- **3 rolled-back changes** forced to reopen-and-verify

Blank fields are treated as signals: 191 tickets with no first response, 143
with no confidence score, all counted and reported.

---

## The screens

| Page | What it shows |
|---|---|
| `/` Dashboard | Business outcomes, agent runs, roster, step-by-step run timeline |
| `/elimination` | The differentiator — ranked classes, proposed fixes, deflection |
| `/workbench` | Human-in-the-loop queue. Approve / reject / modify / more info |
| `/data-manager` | 8 integrations with live health |
| `/ai/policies` | 4 editable policies, the evaluation log, the change history |
| `/ai/insights` | 12 insights — clusters, incidents, gaps, SLA forecast |
| AI Manager | Chat over the operation, every answer cited to an Operator |

---

## Design decisions worth defending

**Nothing is invented.** If a value cannot be traced to a source row or an agent
run, it is not shown. Missing inputs are reported as missing rather than
defaulted to zero.

**The Command Center never decides.** Clustering, classification and fix
selection all happen on Auto. This repo reads what the Operators emitted, ranks
it, and shows the provenance — which run, which step, when.

**The AI Manager is not a language model.** Answers are assembled from mirrored
agent data and cite the Operator they came from, so it cannot invent a ticket
number. Round 1 caught Supervity's own chat summaries doing exactly that while
its audit log said otherwise.

**Health is honest.** The Data Manager distinguishes a live probe from health
inferred out of recent agent runs. OneDrive, GitHub and Outlook are reached by
the Operators using their own credentials, so this backend has nothing to probe
and does not pretend otherwise.

**Nothing is hardcoded to the sample data.** No ticket key, person, article id or
expected count appears anywhere in the repo. Judging runs on a hidden dataset
with the same schema.

---

## Open items

| Item | Priority | Notes |
|---|---|---|
| Public URL | ✅ done | https://autopilot-frontend-mafd.onrender.com — free tier sleeps after 15 min idle, so open it shortly before judging |
| Demo video | **High** | 5–10 min per the brief; `DEMO_SCRIPT.md` runs 7 |
| LinkedIn post | **High** | Three drafts ready in `LINKEDIN_POST.md`; same video, tag @Supervity and @Vijay Navaluri |
| Resolve one Workbench item | ✅ done | ITSM-2212 rejected on the deployed site, reason recorded |
| End-to-end auto-resolution | Known gap | The agent decides a ticket is safe (ALLOW at 0.99 standalone) but Auto returns an empty payload from that Operator to the Orchestrator, so batch tickets escalate on the confidence gate instead. Four attempts, three approaches. Two of three escalations in the last cycle were correct policy behaviour regardless |
| Ghost Run | Not started | Replay decisions against the historical backlog. Time went into Operator correctness instead |

All five mandatories are met on the deployed instance, not just locally.

---

## Running it locally

```bash
cd AutoPilot-Template
docker compose up --build -d
```

- Command Center — http://localhost:3001
- API docs — http://localhost:8001/api/docs

Needs `SUPERVITY_API_KEY` in `.env` (not committed). 46 backend tests:

```bash
docker compose exec backend python -m pytest tests/ -q
```

## Where the documents are

| File | Purpose |
|---|---|
| `PROJECT_STATUS.md` | This file — start here |
| `DEMO_SCRIPT.md` | The 4-minute demo, word for word |
| `CLAUDE.md` | Mission, rules, dataset facts, anti-hardcoding constraints |
| `Round2_Trap_Map_and_Plan.md` | Every seeded trap, mapped to actual rows |
| `docs/auto-operators/` | Paste-ready build prompts for every Operator, plus the fix packs |
