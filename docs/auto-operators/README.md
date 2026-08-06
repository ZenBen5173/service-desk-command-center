# Supervity Auto — Operator build prompts (Round 2)

Everything in this folder is **paste-ready text for the Auto chat** at
[auto.supervity.ai](https://auto.supervity.ai). Nothing here runs in this repo.

The hard rule for Round 2: the Orchestrator and every Operator live on Auto.
This repo only displays and governs what Auto decides.

## What already exists on your Auto account

Pulled live from the API on 5 Aug 2026:

| Workflow | Auto ID | Role |
|---|---|---|
| Stalled Ticket Resolver Orchestrator | `019f75d3-b71d-7000-917a-157ebcd43c46` | Manager |
| Ticket Queue Triage Operator | `019f75d2-b5c9-7000-8efb-17d72d2620a6` | Operator 1 |
| Ticket Evidence and Policy Operator | `019f75ad-927c-7000-bb3c-06ff86773d2b` | Operator 2 |
| Safe Resolution and Communication Operator | `019f758f-a7cd-7000-a985-e4901d30a087` | Operator 3 |
| Human Review Escalation Operator | `019f75bc-ea52-7000-9414-3a37e9c3bf0c` | Operator 4 |

All five are Round 1 builds. Round 2 needs **5+ Operators** and they must cope
with the new dataset's traps.

## What to build

| File | Action | Priority |
|---|---|---|
| `01-major-incident-correlator.md` | **Create new** | Must — clears the 5-Operator rule and is the best demo moment |
| `02-change-approval-handler.md` | **Create new** | Must — CAB gating is one of the three required policies |
| `03-csat-knowledge-loop.md` | **Create new** | Strong bonus — self-learning story |
| `04-updates-to-existing-operators.md` | Update the 3 existing | Must — R1 agents miss the R2 traps |
| `05-orchestrator-update.md` | Update the Orchestrator | Must — it has to route to the new Operators |

Build order: 01 → 04 → 02 → 05 → 03.

## How to use these

1. Open [auto.supervity.ai](https://auto.supervity.ai), start a new workflow chat.
2. Paste the whole **Build prompt** block from the file, top to bottom.
3. Let Auto generate the steps, then save it.
4. Run it once with the test inputs listed in the file.
5. Tell Claude Code the new workflow name so the Command Center can pick it up.

For updates to existing Operators, open that workflow in Auto and paste the
**Update prompt** into its chat instead of creating a new one.

## Rules that apply to every Operator here

These are repeated inside each build prompt because Auto reads each one in
isolation. Do not remove them.

- **Never invent a value.** No made-up ticket keys, person names, article IDs or
  confidence scores. If a value cannot be traced to a source row, fail the step
  and escalate.
- **Identity is `account_id` only.** Display names repeat in this dataset.
  Exactly one match or escalate to human review.
- **Dedupe on import** by issue key. The export contains byte-identical
  duplicate rows.
- **Blank is a signal, not an error.** A blank first-response time means no
  first response has happened — that is itself an SLA condition.
- **`customfield_10101` is the assignment group**, not the affected system.
- **`x_auto_safe` on a KB article gates auto-remediation.** No auto-fix without it.
- **SLA is business hours**, computed against the SLA calendar per region,
  including holidays and timezone — never raw elapsed time.
- **Resolved means Status resolved AND Resolution done.** Anything else is a
  state conflict: actionable, and flagged.
- **No scenario keywords as branch conditions.** Judging runs on a hidden dataset
  with the same schema but different rows. Compute, never assume.

## Where the Round 2 dataset lives

All ten CSV exports were uploaded to OneDrive on 5 Aug 2026 at:

```
/Supevity-Hackathon/Round 2/input/
```

Two things about that path will break a copy-paste if you retype it:

- the root folder is spelled **Supevity**, without the `r`
- **Round 2** contains a space, so it needs URL-encoding when called through the
  Microsoft Graph API

Files present: Issues, Users_Directory, Knowledge_Base, Change_Requests,
CSAT_Surveys, SLA_Calendar, Assets_Access, Ticket_Comments,
Incident_Problem_Links, Team_Roster.

The Operators discover which files exist at runtime rather than assuming this
list, so the judged dataset works without edits.

## Inputs every Operator should expose

Keep these as workflow inputs, not hardcoded values, so the hidden dataset works
without edits:

- `onedrive_folder` — folder holding the CSV exports
- `github_repo` — `owner/repo` for the ticket system of record
- thresholds relevant to that Operator (confidence, cluster size, hours)

## Environment variables

Already configured on your account from Round 1:

- `MICROSOFT_ONEDRIVE_TOKEN`
- `GITHUB_TOKEN`
- `MICROSOFT_OUTLOOK_TOKEN`
