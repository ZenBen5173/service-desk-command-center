"""
AI Insights — the five observations the problem statement asks for.

  recurring known-error clusters across users
  a major incident forming from many tickets
  knowledge gaps where no article exists
  SLA-breach forecasts
  uneven team load

Every insight is assembled from findings the Operators already reported on
Supervity Auto. Nothing new is inferred here: if the agents did not observe it,
there is no insight, and the response says which Operator would produce it.

That constraint matters. An insights page that invents patterns is worse than an
empty one, because it looks equally confident either way.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun, AgentWorkflow
from ..models.workbench import WorkbenchException
from .elimination import FIELD_ALIASES, _first

log = logging.getLogger(__name__)

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _parse_output(outputs: Any) -> Any:
    if outputs is None:
        return None
    if isinstance(outputs, str):
        try:
            return json.loads(outputs)
        except (ValueError, TypeError):
            return None
    if not isinstance(outputs, dict):
        return outputs
    inner = outputs.get("output", outputs)
    if isinstance(inner, str):
        try:
            return json.loads(inner)
        except (ValueError, TypeError):
            return None
    return inner


def _payloads(activity: AgentActivity) -> list:
    found = []
    inline = _parse_output(activity.outputs)
    if inline is not None:
        found.append(inline)
    if activity.artifact_data:
        found.extend(activity.artifact_data.values())
    return found


def _walk(node: Any, depth: int = 0) -> Iterable[dict]:
    if depth > 6:
        return
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, depth + 1)


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().rstrip("%"))
        except ValueError:
            return None
    return None


def _newest_runs(db: Session) -> dict[str, int]:
    """Newest run per workflow. Re-running an Operator supersedes the earlier one."""
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    newest: dict[str, int] = {}
    for run in (
        db.query(AgentRun).order_by(AgentRun.auto_created_at.desc().nullslast()).all()
    ):
        key = run.workflow_name or names.get(run.auto_workflow_id) or run.auto_workflow_id
        if key and key not in newest:
            newest[key] = run.id
    return newest


def _classes_and_queue(db: Session) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Pull the Operators' ticket classes and the triage queue.

    Classes come from the Elimination Backlog's own selection, not a second
    implementation of it. Several Operators describe the same tickets from
    different angles — one sizes the problem, another names the permanent fix —
    and picking the widest list on its own landed here on the set with no fixes,
    so this page reported "no permanent fix proposed yet" for classes the
    Elimination page was displaying a fix for. One selection, one answer.

    The triage queue has only one producer, so it is still read directly.
    """
    from .elimination import build_backlog

    classes: list[dict] = []
    sources: dict[str, str] = {}
    try:
        backlog = build_backlog(db, limit=100)
        classes = backlog.get("classes") or []
        if classes:
            origin = (classes[0].get("source") or {}).get("workflow_name")
            sources["classes"] = origin or "an Operator"
    except Exception as exc:  # noqa: BLE001 - insights must degrade, not 500
        log.warning("Could not read the elimination backlog for insights: %s", exc)

    newest = _newest_runs(db)
    if not newest:
        return classes, [], sources

    run_by_id = {r.id: r for r in db.query(AgentRun).all()}
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    activities = (
        db.query(AgentActivity)
        .filter(AgentActivity.run_id.in_(list(newest.values())))
        .all()
    )

    queue: list[dict] = []

    for activity in activities:
        run = run_by_id.get(activity.run_id)
        origin = (
            (run.workflow_name if run else None)
            or (names.get(run.auto_workflow_id) if run else None)
            or "an Operator"
        )
        for payload in _payloads(activity):
            for node in _walk(payload):
                ordered = node.get("ordered_queue")
                if isinstance(ordered, list) and ordered and not queue:
                    queue = [i for i in ordered if isinstance(i, dict)]
                    sources["queue"] = origin

    return classes, queue, sources


# ---------------------------------------------------------------------------
# Action plans
# ---------------------------------------------------------------------------
#
# An insight that names a problem and stops is half an insight. Each one below
# carries a plan: the single next action, who owns it, what it is worth, and the
# ordered steps to get there.
#
# The plans are keyed by action type, never by ticket content — a class about
# printers and a class about mailboxes both take the "eliminate" path, and the
# specifics come from what the Operator reported about that class. Nothing here
# encodes knowledge of the sample dataset.
#
# Where the Operator proposed a permanent fix, that fix is the plan and is
# labelled as the agent's. Where it did not, the plan is a standard service
# management playbook and says so. The distinction is shown in the UI, because a
# reader has to know which sentences came from the agent.

# Roles, not people. The Operators report an owning team when they can; when they
# cannot, naming the function that owns this class of work is still actionable,
# and is marked as coming from the playbook rather than the agent.
FALLBACK_OWNER = {
    "eliminate": "Service Desk Manager with the owning team",
    "incident_command": "Major Incident Manager",
    "author_article": "Knowledge Manager",
    "prioritise": "Service Desk Team Lead",
    "rebalance": "Service Desk Manager",
    "review": "Service Desk Team Lead",
}

EFFORT = {
    "eliminate": "medium",
    "incident_command": "low",
    "author_article": "low",
    "prioritise": "low",
    "rebalance": "medium",
    "review": "low",
}

HORIZON = {
    "eliminate": "this quarter",
    "incident_command": "now",
    "author_article": "this week",
    "prioritise": "now",
    "rebalance": "this week",
    "review": "now",
}


def _steps_for(action_type: str, fix: str | None, agent_proposed: bool) -> list[str]:
    """The ordered path from finding to fixed, per action type."""
    if action_type == "eliminate":
        return [
            "Confirm the root cause with the owning team",
            (
                f"Raise a change request for: {fix}"
                if fix
                else "Agree the permanent fix and raise a change request"
            ),
            "Take it to the change advisory board for approval",
            "Implement, then publish a knowledge article covering it",
            "Watch new ticket volume for this class for two weeks",
        ]
    if action_type == "incident_command":
        return [
            "Declare a major incident and appoint an incident manager",
            "Send one communication to every affected person, not per ticket",
            "Link every member ticket to the parent incident",
            "Fix the root cause, then close the children together",
            "Hold a post-incident review and record the permanent fix",
        ]
    if action_type == "author_article":
        return [
            "Pick a resolved ticket in this class as the source",
            "Draft the article: symptom, cause, steps, verification",
            "Have the owning team review it for accuracy",
            "Publish and mark it auto-safe if the fix carries no risk",
            "Re-check the class in two weeks for repeat tickets",
        ]
    if action_type == "prioritise":
        return [
            "Work the queue in forecast-breach order, not arrival order",
            "Give the tickets with no first response an owner today",
            "Escalate anything that cannot be met inside its calendar",
            "Re-run triage after the queue is cleared",
        ]
    if action_type == "rebalance":
        return [
            "Review the load split with both team leads",
            "Ship the heaviest team's top permanent fix first",
            "Move or cross-train capacity for the remainder",
            "Re-check the split after the fix lands",
        ]
    if action_type == "review":
        return [
            "Sort the Workbench by impact",
            "Clear change approvals first — they block other work",
            "Approve, reject or modify each with a recorded reason",
            "Re-run the cycle so cleared items flow on",
        ]
    return []


def _benefit(action_type: str, data: dict) -> tuple[str, dict]:
    """What the fix is worth, in the agent's own numbers.

    Returns prose plus the structured figures behind it, so the UI can show the
    arithmetic instead of asking anyone to trust the sentence.
    """
    tickets = data.get("tickets")
    breaches = data.get("sla_breaches")
    metric: dict[str, Any] = {}

    if action_type == "eliminate" and tickets:
        metric = {"tickets_prevented": tickets, "sla_breaches_avoided": breaches}
        text = f"{tickets} tickets stop arriving"
        if breaches:
            text += f", and {breaches} SLA breaches stop happening"
        return text, metric

    if action_type == "incident_command" and tickets:
        metric = {"conversations_collapsed": tickets, "responses_needed": 1}
        return (
            f"{tickets} conversations collapse into 1 — one fix, one message, "
            f"{tickets} tickets closed together"
        ), metric

    if action_type == "author_article" and tickets:
        metric = {"tickets_answerable_from_kb": tickets}
        return (
            f"{tickets} tickets become answerable from the knowledge base, and "
            "the class becomes eligible for automated resolution"
        ), metric

    if action_type == "prioritise":
        at_risk = data.get("at_risk_next_8_business_hours")
        no_resp = data.get("no_first_response")
        metric = {"breaches_preventable": at_risk, "tickets_without_first_response": no_resp}
        if at_risk:
            return (
                f"{at_risk} tickets still inside their SLA window can be saved; "
                f"{no_resp or 0} have never been answered"
            ), metric
        return "Breaches stop accumulating while the backlog is worked", metric

    if action_type == "rebalance":
        share = data.get("heaviest_share_pct")
        metric = {"heaviest_share_pct": share}
        return (
            f"Load drops from {share}% concentrated on one team" if share
            else "Load spreads more evenly across teams"
        ), metric

    if action_type == "review":
        metric = {"decisions_outstanding": data.get("open")}
        return (
            f"{data.get('open')} tickets start moving again — each one is blocked "
            "on a decision, not on work"
        ), metric

    return "Not quantified — the Operators did not report the figures needed.", metric


def _plan(
    action_type: str,
    data: dict,
    *,
    agent_fix: str | None = None,
    owning_team: str | None = None,
) -> dict:
    """Assemble the action plan attached to an insight."""
    agent_proposed = bool(agent_fix)
    fix = agent_fix or None
    benefit_text, benefit_metric = _benefit(action_type, data)
    steps = _steps_for(action_type, fix, agent_proposed)

    if fix:
        next_action = fix
    elif steps:
        next_action = steps[0]
    else:
        next_action = "No action derivable from what the Operators reported."

    return {
        "next_action": next_action,
        # Whether the recommendation is the agent's own or a standard playbook
        # step. The UI labels these differently on purpose.
        "next_action_source": "agent" if agent_proposed else "playbook",
        "owner": owning_team or FALLBACK_OWNER.get(action_type, "Service Desk Manager"),
        "owner_source": "agent" if owning_team else "playbook",
        "expected_benefit": benefit_text,
        "benefit_metric": {k: v for k, v in benefit_metric.items() if v is not None},
        "steps": [{"seq": i + 1, "action": s} for i, s in enumerate(steps)],
        "effort": EFFORT.get(action_type),
        "horizon": HORIZON.get(action_type),
    }


def _field(entry: dict, *names: str) -> Any:
    """Resolve a field through the same aliases the Elimination Backlog uses.

    The Operators generate their own key names, so the same class can arrive as
    `proposed_fix` on one run and `recommendation` on the next. Looking only for
    the exact names left this page reporting "No permanent fix proposed yet" for
    classes whose fix was sitting right there under a different key, while the
    Elimination page displayed it correctly off the same payload. Two pages
    disagreeing about the same run is worse than either being sparse.
    """
    for n in names:
        for alias in FIELD_ALIASES.get(n, (n,)):
            value = _first(entry, (alias,))
            if value is not None:
                return value
    return None


def collect(db: Session) -> dict:
    """Build the insight list from what the Operators reported."""
    classes, queue, sources = _classes_and_queue(db)
    insights: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    # --- 1. Recurring known-error clusters across users -------------------
    recurring = [
        c
        for c in classes
        if str(_field(c, "classification", "treatment") or "").upper()
        in ("RECURRING_CLASS", "KNOWLEDGE_GAP", "ARTICLE_INEFFECTIVE")
    ]
    recurring.sort(key=lambda c: _num(_field(c, "member_count", "volume", "ticket_count")) or 0, reverse=True)

    for entry in recurring[:5]:
        volume = int(_num(_field(entry, "member_count", "volume", "ticket_count")) or 0)
        people = _num(_field(entry, "distinct_reporter_count", "distinct_reporters"))
        breaches = _num(_field(entry, "breached_count", "breaches", "breach_count"))
        if volume < 2:
            continue
        agent_fix = _field(entry, "proposed_fix", "permanent_fix")
        team = _field(entry, "owning_team", "assignment_group")
        data = {
            "tickets": volume,
            "people_affected": int(people) if people else None,
            "sla_breaches": int(breaches) if breaches is not None else None,
            "affected_system": _field(entry, "affected_system"),
        }
        insights.append(
            {
                "id": f"recurring::{_field(entry, 'cluster_key', 'class_key', 'key')}",
                "type": "pattern",
                "severity": "warning" if (breaches or 0) > 0 else "info",
                "title": (_field(entry, "label") or "Recurring problem")[:120],
                "description": (
                    f"{volume} tickets from "
                    f"{int(people) if people else 'multiple'} people describe the same "
                    "underlying problem. Resolving them individually repeats the same "
                    "work every time it recurs."
                ),
                "data": data,
                # Never left empty. Where the Operator proposed a fix that is the
                # suggestion; otherwise the playbook's first step stands in, and
                # the plan records which of the two this is.
                "suggested_action": agent_fix
                or "Agree the permanent fix with the owning team and raise a change request.",
                "action_type": "eliminate",
                "owning_team": team,
                "action_plan": _plan(
                    "eliminate", data, agent_fix=agent_fix, owning_team=team
                ),
                "source": sources.get("classes"),
                "created_at": now,
            }
        )

    # --- 2. A major incident forming from many tickets --------------------
    for entry in classes:
        if str(_field(entry, "classification") or "").upper() != "MAJOR_INCIDENT":
            continue
        volume = int(_num(_field(entry, "member_count", "volume")) or 0)
        people = _num(_field(entry, "distinct_reporter_count", "distinct_reporters"))
        languages = _field(entry, "languages") or []
        insights.append(
            {
                "id": f"incident::{_field(entry, 'cluster_key', 'key')}",
                "type": "anomaly",
                "severity": "critical",
                "title": f"Major incident: {(_field(entry, 'label') or 'unnamed cluster')[:90]}",
                "description": (
                    f"{volume} separate tickets from "
                    f"{int(people) if people else 'multiple'} people share one root cause"
                    + (
                        f", reported in {len(languages)} languages"
                        if isinstance(languages, list) and len(languages) > 1
                        else ""
                    )
                    + ". Handled as one incident with a single response rather than "
                    f"{volume} separate conversations."
                ),
                "data": {
                    "tickets": volume,
                    "people_affected": int(people) if people else None,
                    "evidence": _field(entry, "evidence"),
                    "languages": languages if isinstance(languages, list) else None,
                },
                "suggested_action": _field(entry, "proposed_fix")
                or "Run comms once for the whole cluster; do not reply per ticket.",
                "action_type": "incident_command",
                "action_plan": _plan(
                    "incident_command",
                    {"tickets": volume},
                    agent_fix=_field(entry, "proposed_fix"),
                    owning_team=_field(entry, "owning_team", "assignment_group"),
                ),
                "source": sources.get("classes"),
                "created_at": now,
            }
        )

    # --- 3. Knowledge gaps where no article exists ------------------------
    gaps = [
        c
        for c in classes
        if _field(c, "has_kb_article", "kb_match", "article_match") is False
        or str(_field(c, "kb_status") or "").upper() in ("MISSING", "NONE", "NOT_FOUND")
        or str(_field(c, "classification", "treatment") or "").upper() == "KNOWLEDGE_GAP"
    ]
    gaps.sort(key=lambda c: _num(_field(c, "member_count", "volume", "ticket_count")) or 0, reverse=True)
    # Skip anything already listed as a recurring pattern above. The same class
    # qualifying on two counts is one finding, not two rows saying the same
    # thing with different headings.
    already = {i["id"].split("::", 1)[-1] for i in insights}
    gaps = [g for g in gaps
            if str(_field(g, "cluster_key", "class_key", "key")) not in already]
    for entry in gaps[:4]:
        volume = int(_num(_field(entry, "member_count", "volume", "ticket_count")) or 0)
        if volume < 2:
            continue
        insights.append(
            {
                "id": f"gap::{_field(entry, 'cluster_key', 'class_key', 'key')}",
                "type": "recommendation",
                "severity": "warning",
                "title": f"No knowledge article: {(_field(entry, 'label') or 'unnamed class')[:90]}",
                "description": (
                    f"{volume} tickets on this problem and no article covering it. "
                    "Every one was answered from scratch."
                ),
                "data": {"tickets": volume, "articles_found": 0},
                "suggested_action": _field(entry, "proposed_fix")
                or "Draft an article from a resolved ticket in this class.",
                "action_type": "author_article",
                "owning_team": _field(entry, "owning_team"),
                "action_plan": _plan(
                    "author_article",
                    {"tickets": volume},
                    agent_fix=_field(entry, "proposed_fix"),
                    owning_team=_field(entry, "owning_team"),
                ),
                "source": sources.get("classes"),
                "created_at": now,
            }
        )

    # --- 4. SLA-breach forecast -------------------------------------------
    if queue:
        breached = [t for t in queue if t.get("breached") is True]
        at_risk = [
            t
            for t in queue
            if t.get("breached") is not True
            and (_num(t.get("business_hours_remaining")) or 99) <= 8
        ]
        no_response = [t for t in queue if t.get("no_first_response") is True]
        if breached or at_risk:
            insights.append(
                {
                    "id": "sla::forecast",
                    "type": "anomaly",
                    "severity": "critical" if breached else "warning",
                    "title": f"{len(breached)} tickets already breached, {len(at_risk)} within 8 business hours",
                    "description": (
                        "Measured on each region's working calendar including holidays "
                        "and timezone, not raw elapsed time. "
                        f"{len(no_response)} of the queue have had no first response at all."
                    ),
                    "data": {
                        "breached": len(breached),
                        "at_risk_next_8_business_hours": len(at_risk),
                        "no_first_response": len(no_response),
                        "queue_size": len(queue),
                    },
                    "action_plan": _plan(
                        "prioritise",
                        {
                            "at_risk_next_8_business_hours": len(at_risk),
                            "no_first_response": len(no_response),
                        },
                    ),
                    "suggested_action": (
                        "Work the queue in forecast-breach order. The Triage Operator "
                        "already sorts it that way."
                    ),
                    "action_type": "prioritise",
                    "source": sources.get("queue"),
                    "created_at": now,
                }
            )

    # --- 5. Uneven team load ----------------------------------------------
    team_counts: dict[str, int] = {}
    for entry in classes:
        team = _field(entry, "owning_team", "assignment_group")
        volume = int(_num(_field(entry, "member_count", "volume", "ticket_count")) or 0)
        if team and volume:
            team_counts[str(team)] = team_counts.get(str(team), 0) + volume

    if len(team_counts) >= 2:
        ranked = sorted(team_counts.items(), key=lambda kv: kv[1], reverse=True)
        heaviest, heaviest_count = ranked[0]
        lightest, lightest_count = ranked[-1]
        total = sum(team_counts.values())
        share = round(100.0 * heaviest_count / total, 1) if total else 0
        # Only worth flagging when the split is genuinely lopsided.
        if share >= 30 and heaviest_count >= 2 * max(lightest_count, 1):
            insights.append(
                {
                    "id": "load::imbalance",
                    "type": "pattern",
                    "severity": "info",
                    "title": f"{heaviest} carries {share}% of classified ticket volume",
                    "description": (
                        f"{heaviest} owns {heaviest_count} tickets across the classified "
                        f"problems; {lightest} owns {lightest_count}. Load is uneven "
                        "before any of the permanent fixes ship."
                    ),
                    "data": {
                        "by_team": dict(ranked),
                        "heaviest_share_pct": share,
                    },
                    "action_plan": _plan(
                        "rebalance",
                        {"heaviest_share_pct": share},
                        owning_team=heaviest,
                    ),
                    "suggested_action": (
                        f"Fixing {heaviest}'s top problem class removes the largest "
                        "single block of recurring work."
                    ),
                    "action_type": "rebalance",
                    "source": sources.get("classes"),
                    "created_at": now,
                }
            )

    # --- 6. Human decisions still outstanding -----------------------------
    open_items = (
        db.query(WorkbenchException).filter(WorkbenchException.status == "open").count()
    )
    if open_items:
        insights.append(
            {
                "id": "workbench::backlog",
                "type": "recommendation",
                "severity": "warning" if open_items > 20 else "info",
                "title": f"{open_items} items waiting on a human decision",
                "description": (
                    "The agent has done what it safely can on these and stopped. "
                    "Nothing moves until someone decides."
                ),
                "data": {"open": open_items},
                "suggested_action": "Clear the Workbench queue, highest impact first.",
                "action_type": "review",
                "action_plan": _plan("review", {"open": open_items}),
                "source": "Workbench",
                "created_at": now,
            }
        )

    insights.sort(key=lambda i: SEVERITY_ORDER.get(i["severity"], 3))

    missing: list[str] = []
    if not classes:
        missing.append(
            "No ticket classes yet — run the Major-Incident Correlator or the "
            "CSAT and Knowledge Loop Operator."
        )
    if not queue:
        missing.append("No triage queue yet — run the Ticket Queue Triage Operator.")

    return {
        "insights": insights,
        "counts": {
            "total": len(insights),
            "critical": sum(1 for i in insights if i["severity"] == "critical"),
            "warning": sum(1 for i in insights if i["severity"] == "warning"),
            "info": sum(1 for i in insights if i["severity"] == "info"),
        },
        "sources": sources,
        "missing": missing,
        "generated_at": now,
    }
