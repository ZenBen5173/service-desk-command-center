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
    """Pull the Operators' ticket classes and the triage queue from the newest runs."""
    newest = _newest_runs(db)
    if not newest:
        return [], [], {}

    run_by_id = {r.id: r for r in db.query(AgentRun).all()}
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    activities = (
        db.query(AgentActivity)
        .filter(AgentActivity.run_id.in_(list(newest.values())))
        .all()
    )

    best_classes: list[dict] = []
    queue: list[dict] = []
    sources: dict[str, str] = {}

    for activity in activities:
        run = run_by_id.get(activity.run_id)
        origin = (
            (run.workflow_name if run else None)
            or (names.get(run.auto_workflow_id) if run else None)
            or "an Operator"
        )
        for payload in _payloads(activity):
            for node in _walk(payload):
                for key in ("clusters", "classes"):
                    value = node.get(key)
                    if (
                        isinstance(value, list)
                        and value
                        and all(isinstance(i, dict) for i in value)
                    ):
                        # Widest coverage wins, same rule the Elimination
                        # Backlog uses, so the two pages never disagree.
                        if len(value) > len(best_classes):
                            best_classes = value
                            sources["classes"] = origin
                ordered = node.get("ordered_queue")
                if isinstance(ordered, list) and ordered and not queue:
                    queue = [i for i in ordered if isinstance(i, dict)]
                    sources["queue"] = origin

    return best_classes, queue, sources


def _field(entry: dict, *names: str) -> Any:
    for n in names:
        if entry.get(n) is not None:
            return entry[n]
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
        insights.append(
            {
                "id": f"recurring::{_field(entry, 'cluster_key', 'class_key', 'key')}",
                "type": "pattern",
                "severity": "warning" if (breaches or 0) > 0 else "info",
                "title": (_field(entry, "summary", "label", "name") or "Recurring problem")[:120],
                "description": (
                    f"{volume} tickets from "
                    f"{int(people) if people else 'multiple'} people describe the same "
                    "underlying problem. Resolving them individually repeats the same "
                    "work every time it recurs."
                ),
                "data": {
                    "tickets": volume,
                    "people_affected": int(people) if people else None,
                    "sla_breaches": int(breaches) if breaches is not None else None,
                    "affected_system": _field(entry, "affected_system"),
                },
                "suggested_action": _field(entry, "proposed_fix", "permanent_fix")
                or "No permanent fix proposed yet.",
                "action_type": "eliminate",
                "owning_team": _field(entry, "owning_team", "assignment_group"),
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
                "title": f"Major incident: {(_field(entry, 'summary', 'label') or 'unnamed cluster')[:90]}",
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
    for entry in gaps[:4]:
        volume = int(_num(_field(entry, "member_count", "volume", "ticket_count")) or 0)
        if volume < 2:
            continue
        insights.append(
            {
                "id": f"gap::{_field(entry, 'cluster_key', 'class_key', 'key')}",
                "type": "recommendation",
                "severity": "warning",
                "title": f"No knowledge article: {(_field(entry, 'summary', 'label') or 'unnamed')[:90]}",
                "description": (
                    f"{volume} tickets on this problem and no article covering it. "
                    "Every one was answered from scratch."
                ),
                "data": {"tickets": volume, "articles_found": 0},
                "suggested_action": _field(entry, "proposed_fix")
                or "Draft an article from a resolved ticket in this class.",
                "action_type": "author_article",
                "owning_team": _field(entry, "owning_team"),
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
