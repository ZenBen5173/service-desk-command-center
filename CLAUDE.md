# Autopilot Asia 2026 — Round 2 Finals · Service Desk Command Center

## Mission
Build the coded Command Center that wraps a Supervity Auto agent for an IT service desk.
Track 3, Customer Support. Deadline: today.

## HARD RULE — do not break this
- The Orchestrator and all Operators MUST live on Supervity Auto (auto.supervity.ai).
- Never reimplement agent logic in this repo. Rule: "Don't rebuild the Orchestrator or Operators outside Supervity Auto."
- This repo = frontend + backend + database only. It displays and governs; Auto decides and acts.

## What runs where
| Layer | Where |
|---|---|
| Orchestrator + 5 Operators | Supervity Auto (pasted by hand into Auto chat) |
| Command Center, AI Policies, AI Insights, AI Manager, Data Manager, Workbench | THIS repo |
| Source data | OneDrive (live integration, read by Auto) |
| Ticket system of record | GitHub Issues (private repo, already built + tested in Round 1) |
| Channel | Microsoft Outlook |

Template: github.com/digitamizers/AutoPilot-Template — clone, `docker compose up` (backend + database + Command Center shell).
Workflow API key: auto.supervity.ai/u/api-keys · Docs: auto.supervity.ai/docs

## The 5 mandatories (miss one = eliminated)
1. Orchestrator + **≥5 distinct Operators** on Auto, with parallel/branching/stateful behavior.
2. Command Center wired to the Auto agent through the backend API, showing **live** agent activity — not template demo data.
3. **≥3 AI Policies** that measurably change agent behavior, editable without code, every evaluation logged.
4. **≥1 live exception** routed to the Workbench with full context and resolved there.
5. **≥3 live integrations** across 2 categories, visible and healthy in the Data Manager.

## Judged on
Business output 40 · Customizability 20 · Technical architecture 20 · Demo 20.
Metrics: MTTR, SLA compliance, auto-resolution rate, CSAT.
Judging runs on a **hidden dataset** with the same schema. Never hardcode to sample values.

## OUR DIFFERENTIATOR — build this first, lead the demo with it
**Problem Elimination (deflection), not just ticket resolution.**
Everyone else closes tickets faster. We make classes of ticket stop existing.

- Cluster tickets by symptom + root cause **across weeks**, not just a burst window.
- Score each class: volume x breaches x CSAT damage x handling hours. Rank them.
- Classify: many users/one symptom = systemic fix · one user repeating = the fix failed, replace the asset · no KB article = knowledge gap.
- Propose the permanent fix: raise a Change Request (CAB), draft the KB article, name the owning team.
- Human approves at the Workbench. The agent never ships a systemic change alone.
- Report **deflection rate** — tickets prevented. No other team will show this number.

Command Center needs an **Elimination Backlog** panel: ranked ticket classes, cost of each, proposed permanent fix, deflection forecast.

Second differentiator if time allows — **Ghost Run**: replay agent decisions against the historical backlog and show what would have been saved (breaches avoided, MTTR delta). Same aggregation plumbing as above.

## Dataset facts (proven, from the supplied pack — for the hidden set, compute don't assume)
- 462 issues, 97 users, 173 access records, 38 KB articles, 277 comments, 87 CSAT, 13 change requests, 31 incident links, 5 SLA regions, 12 roster members.
- Top recurring classes: shared drive access 44 (11 breached) · printer offline 43 · software install 40 · mailbox full 40 · guest wifi 40 · laptop slow 38 · password reset 38 (avg CSAT 2.7, worst class).
- Repeat offenders: Marcus Iyer "laptop running slow" x4, Wei Yeoh "monitor flickering" x4 — the fix never worked.
- Major incident: INC-9001, 23 payroll-portal tickets one root cause, incl. the same complaint in EN/ES/ZH/FR. INC-9002 = 7 SSO-loop tickets.
- 58 Status/Resolution conflicts. 2 byte-identical duplicate rows (ITSM-2186, ITSM-2219) — dedupe on import.
- 4 date formats in Created. Blank fields are signals, not errors.
- Duplicate display names (Siti Lee, Mei Lee, Ismail Cheng) — identity by account_id only, exactly-one-match or escalate.
- SLA must be computed on business hours/holidays per SLA_Calendar, not raw elapsed time.
- `customfield_10101` = assignment group, NOT the affected system. `x_auto_safe` gates auto-remediation.

Full detail: see `Round2_Trap_Map_and_Plan.md` in this folder.

## The 3 AI Policies (minimum)
1. **Auto-remediation gate** — allow only if KB match has x_auto_safe=true AND confidence >= threshold (default 0.85, editable) AND no CAB required AND action is not an access change.
2. **SLA / VIP priority** — SLA on business hours per region; VIP fast-track; after-hours handling; breach-forecast ordering.
3. **Change control** — open Change Request needing CAB blocks remediation; status Rolled Back forces reopen + verification.

Every evaluation must be logged and visible in the UI. A threshold edit must visibly change agent behavior on the next run (this is a demo moment).

## Build order for today
1. Clone template, `docker compose up`, confirm it boots.
2. Wire API key; get ONE real number from Auto onto the Command Center.
3. Elimination Backlog panel (the differentiator).
4. Policies UI — editable, persisted, logged.
5. Workbench queue — exception in, decision out.
6. Insights + Data Manager.
7. Rehearse demo, record 3–5 min.

## Known platform gotcha (from Round 1)
Supervity's chat summaries contradicted its own Activity Timeline — it invented ticket numbers, identities and confidence values. Trust the audit log / Activity Timeline, never the natural-language summary. Surface authoritative JSON in the UI.

## Anti-hardcoding
Never bake in: issue keys, person names, KB article IDs, expected counts, predetermined decisions, scenario keywords as branch conditions.
Allowed config: runtime inputs, file paths, repo names, thresholds, field mappings, generic policy definitions.
If a value can't be traced to a real source, fail and escalate — never generate it.

## Submission
Public Operator URL · public 3–5 min demo video, no login wall · LinkedIn post with the same video · tag @Supervity and @Vijay Navaluri · #AIEmployees #Supervity #SupervityAI #NoCode #AgenticAI #AutopilotHackathon
