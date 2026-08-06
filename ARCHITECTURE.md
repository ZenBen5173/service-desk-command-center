# Architecture

Service Desk Command Center · Autopilot Asia 2026 Round 2 · Track 3

The organising rule, and the one that shapes every diagram below: **Supervity
Auto decides and acts; this repo displays and governs.** No clustering, no
classification, no policy verdict is computed here. The Command Center reads
what the Operators emitted, ranks it, and shows which run produced it.

---

## 1 · The whole system

```mermaid
graph TB
    subgraph SRC["Source systems"]
        OD["Microsoft OneDrive<br/><i>ticket export, 10 tables</i>"]
        GH["GitHub Issues<br/><i>system of record</i>"]
        OL["Microsoft Outlook<br/><i>channel</i>"]
    end

    subgraph AUTO["Supervity Auto — the agents"]
        ORCH["Service Desk Orchestrator"]
        OPS["7 Operators<br/><i>see section 2</i>"]
        ORCH -->|delegates| OPS
        OPS -->|reports| ORCH
    end

    subgraph CC["Command Center — this repo"]
        API["FastAPI backend<br/><i>mirror + govern</i>"]
        DB[("PostgreSQL<br/><i>mirrored runs,<br/>policies, decisions</i>")]
        UI["Next.js frontend<br/><i>6 surfaces</i>"]
        API <--> DB
        UI --> API
    end

    HUMAN(["Human<br/>reviewer"])

    OD -->|read by Operators| AUTO
    AUTO -->|writes incidents,<br/>approvals, articles| GH
    AUTO -->|replies to requesters| OL

    API -->|"polls workflows,<br/>runs, timelines"| AUTO
    UI -->|"thresholds edited here<br/>become inputs there"| API

    UI <--> HUMAN
    HUMAN -->|"approve / reject,<br/>recorded against the<br/>agent's recommendation"| UI

    classDef auto fill:#1e3a5f,stroke:#4a90d9,color:#fff
    classDef repo fill:#2d4a3e,stroke:#5cb85c,color:#fff
    classDef ext fill:#4a3a2d,stroke:#d9a44a,color:#fff
    classDef person fill:#4a2d4a,stroke:#c77dc7,color:#fff
    class ORCH,OPS auto
    class API,DB,UI repo
    class OD,GH,OL ext
    class HUMAN person
```

**Why the arrow from the Command Center to Auto is one-way for decisions.** The
backend reads run history; it never posts a verdict back. The only influence it
has is through *policy parameters* — a threshold edited in the UI becomes an
input on the Orchestrator's next run. That keeps the audit trail single-sourced:
if a decision exists, an Operator made it.

---

## 2 · The agent cycle

One Orchestrator delegating to seven Operators. Correlation and triage start
together; the run then branches three ways on the decision.

```mermaid
flowchart TB
    START(["Cycle trigger<br/><i>OneDrive folder, GitHub repo,<br/>max tickets, thresholds</i>"])

    subgraph PAR["Parallel start"]
        direction LR
        CORR["Major-Incident Correlator<br/><i>groups by root cause<br/>across weeks</i>"]
        TRI["Ticket Queue Triage<br/><i>business-hours SLA,<br/>VIP fast-track</i>"]
    end

    REC["Reconcile and filter<br/><i>drop tickets already<br/>inside an incident</i>"]

    subgraph PERTICKET["Per ticket"]
        direction TB
        EV["Ticket Evidence and Policy<br/><i>identity, KB match,<br/>asset, access</i>"]
        CA["Change-Approval Handler<br/><i>open CAB blocks;<br/>rollback forces reopen</i>"]
        EV --> CA
    end

    ROUTER{"Decision router<br/><i>precedence:<br/>change control ><br/>access change ><br/>confidence</i>"}

    SAFE["Safe Resolution<br/>and Communication"]
    ESC["Human Review<br/>Escalation"]
    BLOCK["Approval queue"]

    WB[["Workbench<br/><i>human decides</i>"]]
    CSAT["CSAT and Knowledge Loop<br/><i>scores by class,<br/>drafts articles</i>"]

    START --> PAR
    CORR --> REC
    TRI --> REC
    REC --> PERTICKET
    PERTICKET --> ROUTER

    ROUTER -->|"safe to automate"| SAFE
    ROUTER -->|"confidence not<br/>established"| ESC
    ROUTER -->|"blocked on approval"| BLOCK

    ESC --> WB
    BLOCK --> WB
    SAFE --> CSAT
    WB --> CSAT

    classDef op fill:#1e3a5f,stroke:#4a90d9,color:#fff
    classDef gate fill:#5a3a1e,stroke:#d99a4a,color:#fff
    classDef human fill:#4a2d4a,stroke:#c77dc7,color:#fff
    class CORR,TRI,EV,CA,SAFE,ESC,CSAT op
    class ROUTER,BLOCK gate
    class WB human
```

**Four independent reasons the agent stops**, in precedence order — an open
change request outranks everything, then an access or entitlement change, then
unresolved requester identity, then confidence below the gate. None can be
overridden by urgency: a Highest-priority breached ticket was held back because
two employees share a display name.

---

## 3 · How a policy change reaches the agent

The demo moment: edit a threshold, and the next run behaves differently. No
code, no workflow rebuild.

```mermaid
sequenceDiagram
    actor H as Human
    participant UI as AI Policies page
    participant API as Backend
    participant DB as PostgreSQL
    participant AUTO as Supervity Auto

    H->>UI: change confidence gate 0.85 → 0.95
    UI->>API: PATCH /api/policies/{id}
    API->>DB: persist value + who changed it + when
    Note over DB: change history is append-only

    H->>UI: run the Orchestrator
    UI->>API: execute workflow
    API->>DB: read effective policy parameters
    API->>AUTO: start run with those as inputs
    Note over AUTO: Operators evaluate against<br/>the threshold now in force

    AUTO-->>API: run + timeline
    API->>DB: ingest every evaluation
    Note over DB: rule fired, threshold at the time,<br/>what it was compared against
    API-->>UI: evaluation log
    UI-->>H: the same ticket now escalates
```

Every evaluation is stored with the threshold that applied *at that moment*, so
a later edit never rewrites history.

---

## 4 · Where the data lives

```mermaid
erDiagram
    AGENT_WORKFLOW ||--o{ AGENT_RUN : "has runs"
    AGENT_RUN ||--o{ AGENT_ACTIVITY : "has steps"
    AGENT_ACTIVITY ||--o{ POLICY_EVALUATION : "produced"
    AGENT_ACTIVITY ||--o{ WORKBENCH_EXCEPTION : "raised"
    POLICY ||--o{ POLICY_EVALUATION : "evaluated as"
    POLICY ||--o{ POLICY_CHANGE : "was edited"
    WORKBENCH_EXCEPTION ||--o| WORKBENCH_DECISION : "resolved by"

    AGENT_WORKFLOW {
        string auto_id "id on Supervity Auto"
        string name
        string role "orchestrator | operator"
    }
    AGENT_RUN {
        string status
        int duration_seconds
        string timeline_error "null unless Auto 404s"
    }
    AGENT_ACTIVITY {
        int sequence
        json outputs "the authoritative JSON"
        json artifact_data "downloaded reports"
    }
    POLICY_EVALUATION {
        string verdict
        float threshold_in_force
        string compared_against
    }
    WORKBENCH_EXCEPTION {
        string exception_type
        json evidence "what stopped the agent"
        string recommendation
    }
```

Runs deleted on Auto are pruned here rather than lingering, so the Operator
count on screen is always what actually exists.

---

## 5 · Integrations

Eight, discovered from the workflows on Auto rather than declared in config —
connect something new there and it appears in the Data Manager.

| Category | Integration | Health basis |
|---|---|---|
| Agent Platform | Supervity Auto | direct probe |
| Data Source | Microsoft OneDrive | inferred from agent runs |
| System of Record | GitHub Issues | inferred from agent runs |
| Communication | Microsoft Outlook | inferred from agent runs |
| Database | PostgreSQL | direct probe |
| Human-in-the-loop | Human Input Form | inferred from agent runs |
| Storage | Output Artifacts | inferred from agent runs |
| AI | Language Model | inferred from agent runs |

The Data Manager labels which is which. OneDrive, GitHub and Outlook are reached
by the Operators using their own credentials, so this backend has nothing to
probe — claiming a live check it cannot make would be a lie, and a degraded
badge here means runs using that integration actually failed.

---

## 6 · Design decisions worth defending

**Nothing is invented.** If a value cannot be traced to a source row or an agent
run, it is not displayed. MTTR is blank with the reason printed beside it: no
Operator reports resolution timestamps, and the Command Center does not compute
metrics the agents have not produced. A dash is honest; a zero is a claim.

**Deflection is two numbers, never blended.** Tickets already collapsed into a
single incident are avoided work. Tickets targeted by a proposed permanent fix
are a forecast, conditional on a human approving it. Adding them together would
produce a better headline and a worse answer.

**The AI Manager holds no model.** Answers are assembled from mirrored agent
output and cite the Operator they came from; a question outside that data gets
"I can't answer that from agent data" rather than a plausible guess. Round 1
caught Supervity's own chat summaries inventing ticket numbers while its audit
log said otherwise — this surface cannot repeat that failure.

**AI Insights re-presents, it does not analyse.** The clustering that recognised
the same payroll complaint in four languages happened inside the Correlator on
Auto. This page ranks those findings and names the run that produced each.

**Nothing is hardcoded to the sample data.** No ticket key, person, article id
or expected count appears anywhere in the repo. Field-name aliases are mapped,
because the agent generates its own key names — but no value is.
