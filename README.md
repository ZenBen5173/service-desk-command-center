# Service Desk Command Center

**Autopilot Asia 2026 · Round 2 · Track 3, Customer Support**

Everyone else closes tickets faster. This makes classes of ticket stop existing —
and reports the number.

🔗 **Live:** https://autopilot-frontend-mafd.onrender.com
*(free tier — the first load after an idle spell takes about a minute to wake)*

---

## What it is

An IT service desk run by an AI Employee. The Orchestrator and seven Operators
live on **Supervity Auto**; this repository is the Command Center that displays,
governs and audits them.

The organising rule, and the one that shapes everything here: **Auto decides and
acts; this repo displays and governs.** No clustering, no classification, no
policy verdict is computed in this codebase. It reads what the Operators emitted,
ranks it, and shows which run produced it.

## The differentiator: Problem Elimination

Resolving forty-four shared-drive requests quickly is being efficient at
something that shouldn't be happening. So the agents look underneath the queue:

- Cluster tickets by **root cause across weeks**, not a burst window
- Rank each class by what it costs — volume, breaches, satisfaction damage
- Propose the **permanent fix**, name the owning team, draft the article
- A human approves before anything ships

**Deflection is reported as two numbers, never blended:** tickets already
collapsed into a single incident (avoided work), and tickets a proposed fix would
prevent (a forecast, labelled as one). Adding them together would produce a
better headline and a worse answer.

## Current state

| | |
|---|---|
| Agents | 1 Orchestrator + 7 Operators on Supervity Auto |
| Agent runs mirrored | 96 · 97.8% success |
| Ticket classes found | 15, covering all 460 tickets |
| Deflection | 75 collapsed · 380 preventable |
| Policy evaluations logged | 9,752 |
| Workbench | 177 items awaiting a human |
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

## Design decisions worth defending

**Nothing is invented.** If a value cannot be traced to a source row or an agent
run, it is not displayed. MTTR is deliberately blank with the reason printed
beside it — no Operator reports resolution timestamps, and this repo does not
compute metrics the agents have not produced. A dash is honest; a zero is a claim.

**The AI Manager holds no language model.** Answers are assembled from mirrored
agent output; a question outside that data gets "I can't answer that from agent
data" rather than a plausible guess. Round 1 caught the platform's own chat
summaries inventing ticket numbers while its audit log said otherwise.

**Health is honest.** The Data Manager separates a direct probe from health
inferred out of recent runs. OneDrive, GitHub and Outlook are reached by the
Operators with their own credentials, so this backend has nothing to probe and
does not pretend otherwise.

**Nothing is hardcoded to the sample data.** No ticket key, person, article id or
expected count appears anywhere in this repository. Judging runs on a hidden
dataset with the same schema.

## Documentation

| File | What's in it |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System, agent cycle, policy round-trip, schema — as diagrams |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | Where the build stands, deliverable by deliverable |
| [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) | The 7-minute demo, word for word |
| [`DEPLOY.md`](DEPLOY.md) | Getting a stable public URL |
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
