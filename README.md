# Service Desk Command Center

**Autopilot Asia 2026 · Round 2 · Track 3, Customer Support**

Everyone else closes tickets faster. This makes classes of ticket stop existing —
and reports the number.

🔗 **Live:** https://autopilot-frontend-mafd.onrender.com
*(free tier — the first load after an idle spell takes about a minute to wake)*

---

## Three things that make this different

Most service desk agents optimise the queue. This one goes after three other
problems.

### 1. Stop the tickets happening at all

Resolving 44 shared-drive requests quickly is being efficient at something that
should not exist. So instead of working the queue, the agents work out what keeps
filling it:

- Cluster by **root cause across weeks**, not a burst window
- Rank each class by what it actually costs: volume, breaches, satisfaction damage
- Propose the **permanent fix**, name the owning team, draft the missing article
- A human approves before anything ships

**Worked example.** 37 people raised a password reset ticket. A normal service
desk resolves 37 tickets. This agent noticed they are one problem, checked the
knowledge base, found no self-service route existed, and proposed the fix:

> *Implement a Self-Service Password Reset portal integrated with MFA, so users
> verify their own identity and reset credentials without help desk
> intervention.* — owner: IAM Team

Ship that and those 37 tickets stop arriving. Not resolved faster. Gone. The same
logic runs across all 15 classes: shared drive access is 44 tickets that a
Group Policy drive mapping plus a self-service permissions portal would remove;
printers offline is 43 that SNMP monitoring and a universal print driver would
remove.

**460 tickets turned out to be 15 root causes. 380 of them are preventable.**
Reported as two figures that are never blended: **75 already collapsed** into
single incidents (work avoided today), and **380 preventable** if the proposed
fixes ship (a forecast, labelled as one). Adding them together would make a
better headline and a worse answer.

→ `/elimination`

### 2. Know when to stop

Four independent reasons the agent refuses to act, in strict precedence: an open
change request outranks everything, then an access or entitlement change, then
unresolved requester identity, then confidence below the gate. **None can be
overridden by urgency.**

**Worked example.** A ticket came in at Highest priority, already past its SLA
deadline, with a known fix available. Every incentive said act. The agent
stopped, because the reporter's display name matched two different employees in
the directory and it could not tell which of them had raised it. Applying a fix
to the wrong person's account to hit a deadline is not a win, so it escalated
with both candidate records attached and waited. **32 tickets** were held back
for that reason alone.

**A second example, a different reason.** ITSM-2212 had a fix ready and an open
change request awaiting board approval. Change control outranks confidence, so
the agent stopped and opened the approval request in GitHub rather than shipping.
A human reviewed it and upheld the block, and that decision is on the record with
its reason.

Every refusal reaches a person with the evidence that stopped the agent and what
it would have done instead. **9,752 policy evaluations** are logged, each naming
the rule, the threshold in force at that moment, and what it was compared
against, so a later edit never rewrites history.

→ `/workbench`, `/ai/policies`

### 3. Never invent a number

**MTTR is deliberately blank**, with the reason printed beside it: no Operator
reports resolution timestamps, and this repository does not compute metrics the
agents have not produced. A dash is honest; a zero is a claim.

The same rule runs through everything. Missing inputs are listed as missing and
confirmed to have contributed nothing. Integration health separates a direct
probe from health inferred out of recent runs. The chat surface holds **no
language model at all** — answers are assembled from mirrored agent output and
cite the Operator they came from, so a question outside that data returns *"I
can't answer that from agent data"* rather than a plausible guess.

**Worked example.** Ask the AI Manager *"what are the top problems?"* and it
answers with the 15 classes and cites the Major-Incident Correlator run that
found them. Ask it *"tell me a joke"* and it replies:

> *I can't answer that from agent data, so I won't guess.*

...then lists what it can actually answer. It holds no language model, so it has
nothing to improvise with.

**The same rule on health.** OneDrive shows as degraded because runs using it
actually failed, and the card says the status was *inferred from recent agent
runs* rather than directly probed, because the Operators reach OneDrive with
their own credentials and this backend has nothing to test.

Round 1 caught the platform's own chat summaries inventing ticket numbers while
its audit log said otherwise. That is the failure this whole design is built
against.

→ `/`, `/data-manager`, AI Manager

---

## What it is

An IT service desk run by an AI Employee. The Orchestrator and seven Operators
live on **Supervity Auto**; this repository is the Command Center that displays,
governs and audits them.

The organising rule, and the one that shapes everything here: **Auto decides and
acts; this repo displays and governs.** No clustering, no classification, no
policy verdict is computed in this codebase. It reads what the Operators emitted,
ranks it, and shows which run produced it.

## Current state

| | |
|---|---|
| Agents | 1 Orchestrator + 7 Operators on Supervity Auto |
| Agent runs mirrored | 96 · 97.8% success |
| Ticket classes found | 15, covering all 460 tickets |
| Deflection | 75 collapsed · 380 preventable |
| Policy evaluations logged | 9,752 |
| Workbench | 176 awaiting a human · 1 resolved |
| Integrations | 8 across 8 categories |
| Backend tests | 46 passing |

## The screens

| Page | What it shows |
|---|---|
| `/` | Business outcomes, agent roster, step-by-step run timelines |
| `/elimination` | The differentiator — ranked classes, proposed fixes, deflection |
| `/workbench` | The human queue: approve · reject · modify · request more info |
| `/ai/policies` | 4 editable policies, the evaluation log, the change history |
| `/ai/insights` | Recurring problems, forming incidents, gaps, breach forecast |
| `/data-manager` | Live integration registry and health |
| AI Manager | Ask the operation questions; every answer cites an Operator |

## One more thing worth defending

**Nothing is hardcoded to the sample data.** No ticket key, person, article id or
expected count appears anywhere in this repository. Classes, fixes and rankings
are computed at runtime from whatever data is present. Field-name aliases are
mapped because the agent generates its own key names, but no value is. Judging
runs on a hidden dataset with the same schema.

## Documentation

| File | What's in it |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System, agent cycle, policy round-trip, schema — as diagrams |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | Where the build stands, deliverable by deliverable |
| [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | The 7-minute demo, word for word |
| [`DEPLOY.md`](DEPLOY.md) | Getting a stable public URL |
| [`LINKEDIN_POST.md`](LINKEDIN_POST.md) | Submission post drafts |
| [`docs/auto-workflows/`](docs/auto-workflows/) | The Orchestrator and all seven Operators, exported from Auto |
| [`docs/auto-operators/`](docs/auto-operators/) | Paste-ready build prompts and fix packs |
| [`Round2_Trap_Map_and_Plan.md`](Round2_Trap_Map_and_Plan.md) | Every seeded trap in the dataset, mapped to real rows |

## Running it locally

```bash
docker compose up --build -d
```

- Command Center — http://localhost:3001
- API docs — http://localhost:8001/api/docs

Needs `SUPERVITY_API_KEY` in `.env` (not committed). Then pull the agent history:

```bash
curl -X POST "http://localhost:8001/api/agent/sync?timeline_limit=60"
```

Tests:

```bash
docker compose exec backend python -m pytest tests/ -q
```

## Stack

Next.js 15 · React 19 · Tailwind · FastAPI · SQLAlchemy 2 · PostgreSQL 15 ·
Docker Compose. Built on the
[AutoPilot Template](https://github.com/digitamizers/AutoPilot-Template).
