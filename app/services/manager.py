"""
AI Manager — ask the operation a question, get an answer from real agent data.

This is deliberately not a language model. Every answer is assembled from what
the Operators reported on Supervity Auto and cites the run it came from. A
chat surface that paraphrases agent output is exactly how Round 1's summaries
ended up inventing ticket numbers; this one can only repeat figures that exist.

If a question cannot be answered from mirrored agent data, it says so and names
the Operator that would produce the answer, rather than guessing.
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.agent import AgentRun, AgentWorkflow
from ..models.policy import Policy, PolicyEvaluation
from ..models.workbench import WorkbenchException
from . import business_metrics, elimination, insights

log = logging.getLogger(__name__)


def _fmt(value, dash: str = "not reported") -> str:
    return dash if value is None else str(value)


# Each intent: the words that select it, and the function that answers it.
# Keyword routing rather than a model, so the mapping from question to data is
# inspectable and cannot drift.
INTENTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "deflection",
        ("deflect", "prevent", "eliminat", "avoid", "collapse", "stop happening",
         "waste", "save", "saving", "reduce"),
    ),
    (
        "workbench",
        ("workbench", "human", "escalat", "waiting", "approval", "approve",
         "queue", "stopped", "stop", "refuse", "blocked", "pending", "review"),
    ),
    (
        "problems",
        ("problem", "class", "cluster", "recurring", "backlog", "worst", "top",
         "biggest", "common", "root cause", "issue", "printer", "password",
         "drive", "wifi", "mailbox", "laptop", "software"),
    ),
    (
        "sla",
        ("sla", "breach", "overdue", "business hour", "late", "on time",
         "deadline", "target", "slow"),
    ),
    ("csat", ("csat", "satisfaction", "happy", "unhappy", "score", "rating", "feedback")),
    (
        "resolution",
        ("auto", "resolv", "allow", "automat", "fix itself", "without a human",
         "unattended"),
    ),
    (
        "policies",
        ("policy", "policies", "rule", "governance", "threshold", "gate",
         "guardrail", "control", "compliance"),
    ),
    (
        "agents",
        ("agent", "operator", "orchestrator", "workflow", "run", "who does",
         "how does it work", "architecture"),
    ),
    (
        "insights",
        ("insight", "anomal", "pattern", "recommend", "knowledge gap",
         "incident", "trend"),
    ),
    (
        "team",
        ("team", "who owns", "owner", "assign", "load", "capacity", "overload",
         "drowning", "hire", "headcount", "staff", "busiest", "workload"),
    ),
    (
        "status",
        ("status", "summary", "overview", "how are", "how's", "everything",
         "health", "doing", "going", "state of"),
    ),
]



# What this surface can answer, in the user's words. Shown verbatim when a
# question falls outside them.
TOPICS = (
    "how the operation is doing overall",
    "the top problems and their proposed fixes",
    "how many tickets we can prevent",
    "SLA compliance and breaches",
    "satisfaction scores",
    "auto-resolution decisions",
    "what is waiting on a human",
    "the policies in force",
    "which team carries the most load",
    "the agents and what they do",
    "the current insights",
)


def _mentions(question: str, word: str) -> bool:
    """Match on a word boundary, not a bare substring.

    Plain `in` routed "why did the agent stop on that laptop ticket" to the
    problems list, because "top" sits inside "laptop". A trailing boundary only
    — so "escalat" still catches escalated and escalation.
    """
    return re.search(r"\b" + re.escape(word), question) is not None


def _route(question: str) -> str | None:
    """Pick the topic, or None when the question falls outside what we hold.

    Returning None rather than defaulting to a summary is deliberate. Answering
    an unmatched question with a confident answer about something else is worse
    than admitting the gap — that is exactly the failure this Command Center was
    built to avoid.
    """
    q = (question or "").lower()
    best, best_hits = None, 0
    for intent, words in INTENTS:
        hits = sum(1 for w in words if _mentions(q, w))
        if hits > best_hits:
            best, best_hits = intent, hits
    return best


def answer(db: Session, question: str) -> dict:
    """Answer a question about the operation from mirrored agent data."""
    intent = _route(question)
    citations: list[str] = []
    suggestions: list[str] = []

    if intent is None:
        return {
            "question": question,
            "intent": "unsupported",
            "answer": (
                "I can't answer that from agent data, so I won't guess. I can "
                "tell you about:\n"
                + "\n".join(f"• {t}" for t in TOPICS)
            ),
            "citations": [],
            "suggestions": [
                "How are we doing?",
                "What are the top problems?",
                "What is waiting on a human?",
            ],
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }

    metrics = business_metrics.collect(db)
    sources = metrics.get("sources", {})

    def cite(key: str) -> None:
        src = sources.get(key)
        if src and src not in citations:
            citations.append(src)

    if intent == "deflection":
        d = metrics.get("deflection") or {}
        collapse = d.get("collapsed_now") or {}
        forecast = d.get("preventable") or {}
        cite("deflection")
        if not collapse and not forecast:
            text = (
                "No deflection has been reported yet. The Major-Incident "
                "Correlator produces those figures."
            )
        else:
            text = (
                f"Two separate numbers, deliberately never added together. "
                f"{_fmt(collapse.get('count'))} tickets have already been collapsed "
                "into single incidents — that handling effort is avoided. A further "
                f"{_fmt(forecast.get('count'))} are forecast preventable if the "
                "proposed permanent fixes ship, which is conditional on a human "
                "approving each one."
            )
        suggestions = ["What are the top problems?", "What fixes were proposed?"]

    elif intent == "problems":
        backlog = elimination.build_backlog(db, limit=5)
        totals = backlog["totals"]
        if not backlog["has_data"]:
            text = (
                "No ticket classes have been reported yet. Run the Major-Incident "
                "Correlator, then sync."
            )
        else:
            lines = [
                f"{totals['classes']} distinct problems account for "
                f"{totals['tickets_in_classes']} tickets. The heaviest:"
            ]
            for i, c in enumerate(backlog["classes"][:5], 1):
                breach = (
                    f", {c['breaches']} breached" if c["breaches"] is not None else ""
                )
                lines.append(f"{i}. {c['label']} — {c['volume']} tickets{breach}")
                if c.get("proposed_fix"):
                    lines.append(f"   Fix: {c['proposed_fix'][:150]}")
            text = "\n".join(lines)
            for c in backlog["classes"][:1]:
                src = (c.get("source") or {}).get("workflow_name")
                if src:
                    citations.append(src)
        suggestions = ["How many tickets can we prevent?", "Which team owns the most?"]

    elif intent == "sla":
        s = metrics.get("sla")
        cite("sla")
        if not s:
            text = (
                "No SLA basis reported yet. The Ticket Queue Triage Operator "
                "produces it."
            )
        else:
            text = (
                f"{s['on_business_hours']} of {s['tickets_measured']} tickets "
                f"({s['authoritative_pct']}%) have an SLA measured on the regional "
                "business-hours calendar, including holidays and timezone. The "
                f"remaining {s['elapsed_fallback']} fall back to raw elapsed time "
                "because the requester's identity could not be resolved to exactly "
                "one account — those are marked, not silently mixed in."
            )
        suggestions = ["How many are breached?", "What is waiting on a human?"]

    elif intent == "csat":
        c = metrics.get("csat")
        cite("csat")
        if not c:
            text = "No satisfaction data yet. The CSAT and Knowledge Loop Operator produces it."
        else:
            text = (
                f"Average satisfaction is {c['average']} out of 5 across "
                f"{int(c['responses'] or 0)} responses, a "
                f"{_fmt(c['response_rate_pct'])}% response rate. Non-responses are "
                "counted separately and never averaged as zero."
            )
        suggestions = ["Which problems have the worst satisfaction?"]

    elif intent == "resolution":
        r = metrics.get("resolution")
        cite("resolution")
        if not r:
            text = "No decisions recorded yet."
        else:
            basis = (
                "across a full Orchestrator cycle"
                if r.get("basis") == "orchestrator_cycle"
                else "from single-ticket Operator runs rather than a full cycle"
            )
            text = (
                f"{r['auto_resolution_rate_pct']}% auto-resolution {basis}: "
                f"{r['allowed']} allowed, {r['human_review']} sent to a human, "
                f"{r['blocked']} blocked. The agent escalates when it cannot "
                "establish confidence rather than acting on a guess."
            )
        suggestions = ["Why was something escalated?", "What is in the Workbench?"]

    elif intent == "workbench":
        open_items = (
            db.query(WorkbenchException)
            .filter(WorkbenchException.status == "open")
            .count()
        )
        resolved = (
            db.query(WorkbenchException)
            .filter(WorkbenchException.status != "open")
            .count()
        )
        by_type: dict[str, int] = {}
        for row in db.query(WorkbenchException).all():
            key = row.exception_type or "unclassified"
            by_type[key] = by_type.get(key, 0) + 1
        top = sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)[:4]
        text = (
            f"{open_items} items are waiting on a human decision and {resolved} "
            "have been resolved. By reason: "
            + ", ".join(f"{k.replace('_', ' ')} ({v})" for k, v in top)
            + ". Each arrives with the evidence that stopped the agent and what it "
            "would have done instead."
        )
        citations.append("Workbench")
        suggestions = ["Why did the agent stop?", "What needs approval?"]

    elif intent == "policies":
        policies = db.query(Policy).all()
        active = [p for p in policies if p.enabled]
        evals = db.query(PolicyEvaluation).count()
        text = (
            f"{len(active)} active policies of {len(policies)} defined, with "
            f"{evals} evaluations logged. Each evaluation records the rule that "
            "fired, the threshold in force at the time, and what it was compared "
            "against. Editing a threshold changes agent behaviour on the next run "
            "with no code change."
        )
        if active:
            text += " Active: " + ", ".join(p.name for p in active[:5]) + "."
        citations.append("Command Center policy store")
        suggestions = ["What blocked the payroll fix?", "Show the auto-resolution gate"]

    elif intent == "agents":
        workflows = db.query(AgentWorkflow).all()
        operators = [w for w in workflows if w.role == "operator"]
        orchestrators = [w for w in workflows if w.role == "orchestrator"]
        runs = db.query(AgentRun).count()
        text = (
            f"{len(orchestrators)} Orchestrator and {len(operators)} Operators on "
            f"Supervity Auto, with {runs} runs mirrored here. Operators: "
            + ", ".join(w.name.replace(" Operator", "") for w in operators)
            + ". The Orchestrator starts correlation and triage in parallel, then "
            "branches on the decision."
        )
        citations.append("Supervity Auto")
        suggestions = ["What did the last run do?", "How do they work together?"]

    elif intent == "insights":
        found = insights.collect(db)
        counts = found["counts"]
        if not found["insights"]:
            text = "No insights yet — the Operators have not reported findings."
        else:
            lines = [
                f"{counts['total']} insights: {counts['critical']} critical, "
                f"{counts['warning']} warning, {counts['info']} info. The most urgent:"
            ]
            for i in found["insights"][:4]:
                lines.append(f"• [{i['severity']}] {i['title']}")
            text = "\n".join(lines)
        suggestions = ["What are the knowledge gaps?", "Which team is overloaded?"]

    elif intent == "team":
        backlog = elimination.build_backlog(db, limit=50)
        by_team: dict[str, int] = {}
        for c in backlog["classes"]:
            team = c.get("owning_team")
            if team and c.get("volume"):
                by_team[str(team)] = by_team.get(str(team), 0) + int(c["volume"])
        if not by_team:
            text = (
                "No Operator has attributed ticket classes to an owning team yet. "
                "The Major-Incident Correlator produces that attribution."
            )
        else:
            ranked = sorted(by_team.items(), key=lambda kv: kv[1], reverse=True)
            total = sum(by_team.values())
            lines = ["Classified ticket volume by owning team:"]
            for team, count in ranked[:6]:
                share = round(100.0 * count / total, 1) if total else 0
                lines.append(f"• {team} — {count} tickets ({share}%)")
            lines.append(
                "This is where the work falls before any of the proposed permanent "
                "fixes ship. Fixing the heaviest team's top class removes the "
                "largest single block of recurring work."
            )
            text = "\n".join(lines)
            for c in backlog["classes"][:1]:
                src = (c.get("source") or {}).get("workflow_name")
                if src:
                    citations.append(src)
        suggestions = ["What are the top problems?", "What fixes were proposed?"]

    else:  # status
        d = metrics.get("deflection") or {}
        collapse = (d.get("collapsed_now") or {}).get("count")
        forecast = (d.get("preventable") or {}).get("count")
        s = metrics.get("sla") or {}
        c = metrics.get("csat") or {}
        open_items = (
            db.query(WorkbenchException)
            .filter(WorkbenchException.status == "open")
            .count()
        )
        runs = db.query(AgentRun).count()
        text = (
            f"{runs} agent runs mirrored. "
            f"SLA measured on business hours for {_fmt(s.get('authoritative_pct'))}% "
            f"of tickets. CSAT {_fmt(c.get('average'))} out of 5. "
            f"{_fmt(collapse)} tickets collapsed into incidents, {_fmt(forecast)} "
            f"forecast preventable. {open_items} items waiting on a human. "
            "MTTR is not shown — no Operator reports resolution timestamps, and "
            "this Command Center does not compute metrics the agents have not "
            "produced."
        )
        for k in ("sla", "csat", "deflection"):
            cite(k)
        suggestions = [
            "What are the top problems?",
            "How many tickets can we prevent?",
            "What is waiting on a human?",
        ]

    return {
        "question": question,
        "intent": intent,
        "answer": text,
        # Which agents the figures came from. An answer with no citation is an
        # answer the Command Center could not ground.
        "citations": citations,
        "suggestions": suggestions,
        "answered_at": datetime.now(timezone.utc).isoformat(),
    }
