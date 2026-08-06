# Round 2 (Finals) — Service Desk Command Center: Data Pack Trap Map
Scanned 5 Aug 2026 · dataset: `support_enterprise_export.xlsx` + 10 CSV tables (~1,200 rows)

## What Round 2 demands (the 5 mandatories)
1. **Agent on Auto**: Orchestrator + **≥5 distinct Operators** (was 2 in R1), parallel/branching/stateful.
2. **Connected Command Center**: coded frontend from `github.com/digitamizers/AutoPilot-Template` (docker compose), wired to the Auto agent via backend API (API key from auto.supervity.ai/u/api-keys), showing LIVE agent activity — not template demo data.
3. **Working AI Policies**: ≥3 active, editable-without-code policies that measurably change behavior, every evaluation logged.
4. **Live human loop**: ≥1 real exception routed to the Workbench with full context and resolved there.
5. **Live integrations**: ≥3 across 2 categories, visible and healthy in the Data Manager.

Outcome metrics: **MTTR, SLA compliance, auto-resolution rate, CSAT.**
R1 stack carries over (per team handoff): GitHub Issues (system of record) + OneDrive (data store) + Outlook (channel); Supabase available as extra system of record. R1 rows are all preserved in this pack (superset).

## Dataset shape
Issues 462 (2 are exact duplicate rows — see T8) · Users 97 · Assets_Access 173 · KB 38 · Ticket_Comments 277 · CSAT 87 · Change_Requests 13 · Incident_Problem_Links 31 · SLA_Calendar 5 regions · Team_Roster 12 members/4 teams.

Field notes: `customfield_10030` = SLA state (Within SLA 206 / At risk 165 / Breached 91). `customfield_10101` = assignment group (NOT the affected system). Status × Resolution define real state. `x_vip` in Users drives prioritization. `x_auto_safe` in KB gates auto-remediation. SLA must be computed against SLA_Calendar business hours/holidays/timezones, not raw elapsed time.

## The 9 seeded traps (from Field_Dictionary) mapped to actual rows

**T1 — Stalled provisioning ticket.** ITSM-2001 (Faizal Das — VIP — "New hire cannot access ERP", waiting 6+ days, At risk) plus the trio ITSM-2206/2207/2208 (same summary, Breached, bounced between wrong teams). Missing access evidence ≠ permission to grant: always human review, never invent access.

**T2 — Recurring known-error across users (VPN/SSO).** INC-9002 cluster: ITSM-2199–2205, seven identical "SSO loop on dashboard login" tickets. KB-103 covers it with `x_auto_safe=true` → the legitimate auto-remediation showcase. KB-100 (VPN after Windows update) same pattern from R1.

**T3 — Mis-routed / bouncing tickets.** ITSM-2206/2207/2208: internal comments literally say "Not our queue, reassigning…", "bounced between teams for two days and nobody owns it". Also ITSM-2010 & ITSM-2070: summary says "Network issue", routed to Network Ops, but the description is a payroll-access problem (the disguised-payroll trap). ITSM-2217 is a password reset sitting in Network Ops. Route by description content + Team_Roster assignment groups, not by the existing (wrong) group.

**T4 — VIP after-hours near breach.** ITSM-2209 (Kenji Tanaka, VIP, created 19:42) and ITSM-2210 (Tariq Lim, VIP, created 20:15) — both Highest priority, Critical escalation risk, At risk, created AFTER business hours (SLA_Calendar: 09:00–18:00). SLA clock must respect business hours; VIP policy must fast-track without skipping safety.

**T5 — MAJOR INCIDENT flood, one root cause (INC-9001).** 23 unique tickets (ITSM-2180–2198, 2223–2226) all "payroll portal / timesheet" symptoms within a short window, linked to parent ITSM-2180 ("MAJOR INCIDENT: Payroll portal outage"). Incident_Problem_Links has the `is caused by` edges. Expected behavior: detect the cluster, open/attach to one parent incident, run comms once — not 23 times.

**T6 — Change/CAB approval before fix.** Change_Requests: CHG-0001–0004 are `Pending CAB Approval` with **no approver** (ITSM-2180, 2211, 2212, 2213 — note 2180 is the major incident: its fix needs CAB!). Policy: cab_approval_required=true + status≠Implemented → the agent must NOT remediate; route to Workbench/approval.

**T7 — Failed remediation rolled back.** CHG-0005/0006/0007 status `Rolled Back` → tickets ITSM-2214/2215/2216 ("Email quota exceeded", Breached, In Progress). The fix didn't stick: verify-after-remediate and reopen, don't close. These pair with KB-101 (email quota, auto_safe=true) — safe article but the rollback proves verification is mandatory.

**T8 — Duplicate tickets, same user.** `duplicates` links: ITSM-2218→2217, ITSM-2220→2219, ITSM-2222→2221 (password resets minutes apart). PLUS two literal duplicate ROWS in Issues.csv: ITSM-2186 and ITSM-2219 each appear twice, byte-identical — import must dedupe by Issue key. Beyond the seeded ones, 68 reporter+summary duplicate groups exist (e.g. Marcus Iyer "Laptop running slow" ×4) — resolve one, link/close the rest.

**T9 — Same issue in different languages.** ITSM-2223 (EN), ITSM-2224 (ES "No puedo acceder al portal de nomina"), ITSM-2225 (ZH "无法访问薪资门户"), ITSM-2226 (FR "Impossible d'acceder au portail de paie") — all `relates to` INC-9001. Language must not defeat clustering or reply templates (reply in the requester's language for bonus).

## Extra hidden mess (not in the seeded list)

- **58 Status/Resolution state conflicts** (Resolution=Done but Status=Open/In Progress/Waiting…) — up from 3 in R1. Canonical rule: resolved = Status resolved AND Resolution Done; conflict = actionable + flag.
- **4 date formats in Created**: ISO datetime (298), "Jul 14 2026" (76), DD/MM/YYYY (53), ISO date (35). Updated is uniformly ISO; 8 blank Due dates.
- **Blank fields as signals**: 27 blank x_channel, 58 blank x_escalation_risk, 143 blank x_confidence, 192 blank first_response_time (= no first response yet — an SLA signal of its own), 11 blank CSAT scores (non-response).
- **Duplicate display names in Users**: Mei Lee ×2, Ismail Cheng ×2, Siti Lee ×2 — identity only by account_id; exactly-one-match rule, else human review (same rule as R1 handoff).
- **Assets_Access**: 42 Pending + 29 Revoked — Revoked/Pending is evidence AGAINST auto-granting anything.
- **KB quality varies**: 38 articles, only 21 auto_safe=true; generic "Known issue N" titles must not produce high-confidence matches (min-confidence threshold policy).
- **CSAT trap**: 17 scores ≤2 (escalate-poor-score follow-up Operator material), 11 non-responses.
- **x_confidence floor is 0.45** — nothing under the default 0.85 auto threshold except a handful; the threshold policy must be the gate, not the data.

## The 3+ AI Policies that practically fall out of this data
1. **Auto-remediation gate**: allow only if KB match has x_auto_safe=true AND confidence ≥ threshold (editable, default 0.85) AND no CAB required AND action class ≠ access change.
2. **SLA/VIP priority**: SLA computed on business hours per SLA_Calendar; VIP (x_vip) escalation and after-hours handling; breach-forecast ordering of the queue.
3. **Change control**: any ticket with an open Change_Request needing CAB → block remediation, route to approval; Rolled Back → reopen + verification required.
(+ escalation matrix by assignment group / on_call from Team_Roster; duplicate-collapse policy.)

## Operator lineup to hit "5+" (extending R1's saved Triage + Evidence/Policy Operators)
1. Ticket Queue Triage (R1, extend: SLA_Calendar business-hours math, channel intake)
2. Ticket Evidence & Policy (R1, extend: change-control + duplicate checks)
3. Major-Incident Correlator (cluster flood → parent incident, INC-9001 pattern, cross-language)
4. Safe Resolution & Communication (remediate via KB, Outlook comms in requester language, verify, rollback path)
5. Change-Approval Handler (CAB queue → Workbench, track approve/reject)
6. CSAT & Knowledge Loop (survey after resolve, escalate ≤2, draft KB article from resolved ticket) ← bonus self-learning
Orchestrator branches ALLOW / HUMAN_REVIEW / DENY exactly as the R1 handoff specifies, now also feeding the Command Center backend API.

## Demo moments guaranteed by this data
- Flood detection: INC-9001's 23 tickets collapse into one incident with one comms thread.
- Safe auto-path: an SSO-loop ticket resolved via KB-103 end to end.
- Human loop: ITSM-2001 (access, missing evidence, VIP) lands in the Workbench and is resolved there.
- Policy edit live: change auto-confidence 0.85→0.95 → the SSO ticket now routes to review instead (mandatory #3 proof).
- Rollback story: ITSM-2214 shows verification catching a failed fix.
