"""
Route agent escalations into the Workbench queue.

Operators on Supervity Auto decide what they cannot safely do alone. This
module reads those escalations out of the mirrored activity timelines and turns
each one into a queue item with its full context attached.

It never invents an exception. If the Operators escalated nothing, the queue is
empty and says so.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun
from ..models.workbench import WorkbenchException

log = logging.getLogger(__name__)

# Collections an Operator may use to report work needing a human. Listing the
# accepted names is field mapping — no ticket, person or decision is named here.
EXCEPTION_COLLECTION_KEYS = (
    "exceptions",
    "human_review",
    "human_review_items",
    "escalations",
    "blocked",
    "reopened",
    "awaiting_approval",
    "needs_human",
    "workbench_items",
)

# A hint at what kind of exception each collection represents, used only when
# the item itself does not say. Presentation, not judgement.
COLLECTION_TYPE_HINT: dict[str, str] = {
    "blocked": "change_approval",
    "reopened": "verification_required",
    "awaiting_approval": "change_approval",
    "escalations": "escalation",
    "human_review": "human_review",
    "human_review_items": "human_review",
    "needs_human": "human_review",
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "subject_ref": (
        "issue_key",
        "ticket_key",
        "subject_ref",
        "ticket",
        "cluster_key",
        "change_key",
        "key",
        "id",
    ),
    "subject_type": ("subject_type", "entity_type", "type"),
    "exception_type": (
        "exception_type",
        "reason_code",
        "category",
        "rule",
        "classification",
        "blocking_rule",
        "state",
    ),
    "title": ("title", "summary", "label", "name", "description", "headline"),
    "reason": ("reason", "rationale", "why", "explanation", "detail", "message", "note"),
    "recommendation": (
        "agent_recommendation",
        "recommendation",
        "proposed_action",
        "proposed_fix",
        "suggested_action",
        "would_have_done",
        "action",
    ),
    "confidence": ("confidence", "agent_confidence", "x_confidence", "match_confidence"),
    "priority": ("priority", "severity", "urgency"),
    "raised_at": ("raised_at", "timestamp", "time", "created_at", "at"),
}


def _first(payload: dict, aliases: Iterable[str]) -> Any:
    for alias in aliases:
        if alias in payload and payload[alias] is not None:
            return payload[alias]
    lowered = {str(k).lower(): v for k, v in payload.items()}
    for alias in aliases:
        value = lowered.get(alias.lower())
        if value is not None:
            return value
    return None


def _as_text(value: Any, limit: int = 2000) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()[:limit] or None
    if isinstance(value, (dict, list)):
        return json.dumps(value)[:limit]
    return str(value)[:limit]


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_output(outputs: Any) -> Any:
    """Auto's envelope: the structured result is a JSON string under `output`."""
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


def _find_exception_collections(node: Any, depth: int = 0) -> list[tuple[str, list]]:
    found: list[tuple[str, list]] = []
    if depth > 6:
        return found
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                str(key).lower() in EXCEPTION_COLLECTION_KEYS
                and isinstance(value, list)
                and value
                and all(isinstance(i, dict) for i in value)
            ):
                found.append((str(key).lower(), value))
            else:
                found.extend(_find_exception_collections(value, depth + 1))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_exception_collections(item, depth + 1))
    return found


def _build_title(raw: dict, subject: str | None, exception_type: str | None) -> str:
    explicit = _as_text(_first(raw, FIELD_ALIASES["title"]), 300)
    if explicit:
        return explicit
    if subject and exception_type:
        return f"{subject} — {exception_type.replace('_', ' ')}"
    if subject:
        return f"{subject} needs review"
    return "Agent escalation"


def ingest_exceptions(db: Session) -> dict:
    """Turn agent escalations into queue items.

    Idempotent by `dedupe_key`, so repeated syncs update rather than duplicate.
    An item a human has already resolved is never reopened by a later sync —
    their decision stands.
    """
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )

    created = updated = skipped_resolved = 0

    for activity, run in rows:
        # Escalations may be inline or inside a downloaded JSON report.
        payloads = [_parse_output(activity.outputs)]
        if activity.artifact_data:
            payloads.extend(activity.artifact_data.values())

        collections: list[tuple[str, list]] = []
        for payload in payloads:
            if payload is not None:
                collections.extend(_find_exception_collections(payload))

        for collection_name, collection in collections:
            for index, raw in enumerate(collection):
                subject = _as_text(_first(raw, FIELD_ALIASES["subject_ref"]), 128)
                exception_type = _as_text(
                    _first(raw, FIELD_ALIASES["exception_type"]), 64
                ) or COLLECTION_TYPE_HINT.get(collection_name, collection_name)

                # Identity: the step that raised it plus what it concerns. Falls
                # back to position so two unnamed items do not collapse into one.
                dedupe_key = (
                    f"{run.auto_run_id}:{activity.id}:{collection_name}:"
                    f"{subject or f'idx{index}'}"
                )

                row = (
                    db.query(WorkbenchException)
                    .filter_by(dedupe_key=dedupe_key)
                    .first()
                )

                if row is not None and row.status != "open":
                    # Already decided by a human. Leave it alone.
                    skipped_resolved += 1
                    continue

                if row is None:
                    row = WorkbenchException(dedupe_key=dedupe_key, status="open")
                    db.add(row)
                    created += 1
                else:
                    updated += 1

                row.exception_type = exception_type
                row.subject_ref = subject
                row.subject_type = _as_text(
                    _first(raw, FIELD_ALIASES["subject_type"]), 64
                )
                row.title = _build_title(raw, subject, exception_type)
                row.reason = _as_text(_first(raw, FIELD_ALIASES["reason"]))
                row.agent_recommendation = _as_text(
                    _first(raw, FIELD_ALIASES["recommendation"])
                )
                row.agent_confidence = _as_float(
                    _first(raw, FIELD_ALIASES["confidence"])
                )
                row.priority = _as_text(_first(raw, FIELD_ALIASES["priority"]), 32)
                # The whole item is kept as context: the human should not have to
                # go back to Auto to understand what they are deciding.
                row.context = raw
                row.auto_run_id = run.auto_run_id
                row.workflow_name = run.workflow_name
                row.step_name = activity.step_name
                row.activity_id = activity.id
                row.raised_at = (
                    _parse_dt(_first(raw, FIELD_ALIASES["raised_at"]))
                    or activity.completed_at
                    or run.auto_created_at
                )
                row.raw_payload = raw

    if created or updated:
        db.commit()

    open_count = (
        db.query(WorkbenchException).filter(WorkbenchException.status == "open").count()
    )
    result = {
        "created": created,
        "updated": updated,
        "left_resolved": skipped_resolved,
        "open": open_count,
        "total": db.query(WorkbenchException).count(),
    }
    if result["total"] == 0:
        result["note"] = (
            "No Operator has escalated anything yet. Exceptions appear here when "
            "an Operator emits an exceptions, blocked, reopened or human_review "
            "array."
        )
    return result


def queue_summary(db: Session) -> dict:
    """Counts for the Workbench header."""
    rows = db.query(WorkbenchException).all()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    resolutions: dict[str, int] = {}
    wait_seconds: list[float] = []

    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        key = row.exception_type or "unclassified"
        by_type[key] = by_type.get(key, 0) + 1
        if row.resolution:
            resolutions[row.resolution] = resolutions.get(row.resolution, 0) + 1
        if row.raised_at and row.resolved_at:
            wait_seconds.append((row.resolved_at - row.raised_at).total_seconds())

    avg_wait = round(sum(wait_seconds) / len(wait_seconds)) if wait_seconds else None

    return {
        "total": len(rows),
        "open": by_status.get("open", 0),
        "resolved": sum(v for k, v in by_status.items() if k != "open"),
        "by_type": by_type,
        "by_status": by_status,
        "by_resolution": resolutions,
        "avg_time_to_decision_seconds": avg_wait,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
