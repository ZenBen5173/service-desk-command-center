"""
Policy store, audit trail, and evaluation ingestion.

The Command Center owns policy *values*; Supervity Auto owns policy
*enforcement*. The link between them is `maps_to_input`: each editable
parameter names the Auto workflow input it feeds, so changing a threshold here
changes what the agent does on its next run without anyone editing a workflow.

Evaluations flow the other way. Operators emit a `policy_evaluations` array
describing every rule they checked; this module mirrors those into the log.
Nothing is ever synthesised locally — an empty log means the agent reported no
evaluations, and that is worth knowing.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun
from ..models.policy import Policy, PolicyChange, PolicyEvaluation

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in policy definitions.
#
# These are generic rule *shapes* with tunable parameters — no ticket key,
# person, article id or expected count appears anywhere, so the same set works
# unchanged against a different dataset. They are seeded once and then fully
# editable in the UI, including being disabled or deleted.
# ---------------------------------------------------------------------------

BUILTIN_POLICIES: list[dict] = [
    {
        "key": "auto_remediation_gate",
        "name": "Auto-remediation gate",
        "category": "Safety",
        "priority": 10,
        "description": (
            "Controls when the agent may fix something without a human. A "
            "knowledge article must be marked safe for automation, the match "
            "confidence must clear the threshold, no change approval may be "
            "outstanding, and the action must not be an access change."
        ),
        "rule_text": (
            "Allow automated remediation only if the matched knowledge article "
            "is flagged safe for automation AND match confidence >= "
            "{min_auto_confidence} AND no related change request is awaiting "
            "approval AND the action class is not an access change. Otherwise "
            "route to human review."
        ),
        "applies_to": ["auto_remediation", "ticket_resolution"],
        "parameters": [
            {
                "name": "min_auto_confidence",
                "label": "Minimum confidence to auto-resolve",
                "type": "number",
                "value": 0.85,
                "default": 0.85,
                "min": 0,
                "max": 1,
                "step": 0.01,
                "help": (
                    "Raise this and borderline tickets stop auto-resolving and "
                    "go to review instead. The clearest way to show a policy "
                    "edit changing agent behaviour."
                ),
                "maps_to_input": "min_auto_confidence",
            },
            {
                "name": "require_auto_safe_article",
                "label": "Require the article to be marked auto-safe",
                "type": "boolean",
                "value": True,
                "default": True,
                "help": (
                    "Off means the agent may act on articles nobody has "
                    "certified as safe to automate. Leave on."
                ),
                "maps_to_input": "require_auto_safe_article",
            },
            {
                "name": "block_access_changes",
                "label": "Never automate access changes",
                "type": "boolean",
                "value": True,
                "default": True,
                "help": (
                    "Missing access evidence is not permission to grant "
                    "access. Pending or revoked records are evidence against."
                ),
                "maps_to_input": "block_access_changes",
            },
        ],
    },
    {
        "key": "sla_vip_priority",
        "name": "SLA and VIP prioritisation",
        "category": "Prioritisation",
        "priority": 20,
        "description": (
            "How the queue is ordered. SLA is measured on business hours from "
            "the regional calendar rather than raw elapsed time, VIP requesters "
            "are fast-tracked, and tickets are ordered by forecast breach."
        ),
        "rule_text": (
            "Compute SLA against the regional business-hours calendar, not raw "
            "elapsed time. Fast-track VIP requesters when enabled, without "
            "skipping any safety check. Order the queue by soonest forecast "
            "breach, treating a missing first response as its own SLA state."
        ),
        "applies_to": ["triage", "queue_ordering"],
        "parameters": [
            {
                "name": "business_hours_only",
                "label": "Measure SLA on business hours",
                "type": "boolean",
                "value": True,
                "default": True,
                "help": (
                    "A ticket raised in the evening should not burn its SLA "
                    "overnight. Off reverts to raw elapsed time."
                ),
                "maps_to_input": "business_hours_only",
            },
            {
                "name": "vip_fast_track",
                "label": "Fast-track VIP requesters",
                "type": "boolean",
                "value": True,
                "default": True,
                "maps_to_input": "vip_fast_track",
            },
            {
                "name": "vip_requires_approval",
                "label": "VIP actions still need human approval",
                "type": "boolean",
                "value": True,
                "default": True,
                "help": "Priority is not permission. Speed up, do not loosen.",
                "maps_to_input": "vip_requires_approval",
            },
            {
                "name": "breach_forecast_hours",
                "label": "Flag as at-risk this many business hours before breach",
                "type": "number",
                "value": 4,
                "default": 4,
                "min": 0,
                "max": 72,
                "step": 1,
                "maps_to_input": "breach_forecast_hours",
            },
        ],
    },
    {
        "key": "change_control",
        "name": "Change control",
        "category": "Governance",
        "priority": 5,
        "description": (
            "Stops the agent shipping a change that has not been approved. An "
            "outstanding change-advisory-board approval blocks remediation "
            "regardless of confidence, and a rolled-back change forces the "
            "ticket back open for verification."
        ),
        "rule_text": (
            "If a related change request is awaiting change-advisory-board "
            "approval, or has no named approver, block remediation and route "
            "to approval. If a related change request was rolled back, reopen "
            "the ticket and require verification before it may close. A "
            "pending approval outranks confidence."
        ),
        "applies_to": ["auto_remediation", "ticket_closure"],
        "parameters": [
            {
                "name": "block_on_open_cab",
                "label": "Block remediation while approval is outstanding",
                "type": "boolean",
                "value": True,
                "default": True,
                "maps_to_input": "block_on_open_cab",
            },
            {
                "name": "block_on_missing_approver",
                "label": "Treat an unnamed approver as unapproved",
                "type": "boolean",
                "value": True,
                "default": True,
                "maps_to_input": "block_on_missing_approver",
            },
            {
                "name": "reopen_on_rollback",
                "label": "Reopen and verify after a rolled-back change",
                "type": "boolean",
                "value": True,
                "default": True,
                "help": (
                    "A fix that did not hold is worse than no fix, because it "
                    "hides the problem."
                ),
                "maps_to_input": "reopen_on_rollback",
            },
        ],
    },
    {
        "key": "duplicate_and_incident_collapse",
        "name": "Duplicate and incident collapse",
        "category": "Efficiency",
        "priority": 30,
        "description": (
            "Stops the agent handling one problem many times. Near-identical "
            "tickets collapse to a canonical one, and a cluster sharing a root "
            "cause becomes a single incident with one communication."
        ),
        "rule_text": (
            "Collapse near-identical tickets from the same requester to the "
            "earliest, linking the rest. When at least {min_cluster_size} "
            "tickets from more than one requester share a root cause, attach "
            "them to one parent incident and communicate once, not once per "
            "ticket."
        ),
        "applies_to": ["correlation", "communication"],
        "parameters": [
            {
                "name": "duplicate_collapse",
                "label": "Collapse duplicate tickets",
                "type": "boolean",
                "value": True,
                "default": True,
                "maps_to_input": "duplicate_collapse",
            },
            {
                "name": "min_cluster_size",
                "label": "Tickets needed to declare a major incident",
                "type": "number",
                "value": 5,
                "default": 5,
                "min": 2,
                "max": 100,
                "step": 1,
                "help": (
                    "Lower it and more clusters become incidents. Directly "
                    "changes the Elimination Backlog on the next run."
                ),
                "maps_to_input": "min_cluster_size",
            },
        ],
    },
]


def seed_builtin_policies(db: Session) -> dict:
    """Insert the built-in policies once.

    Existing rows are left alone — an operator's edits must survive a restart,
    so this never overwrites a value that is already in the database.
    """
    created = 0
    for spec in BUILTIN_POLICIES:
        if db.query(Policy).filter_by(key=spec["key"]).first():
            continue
        db.add(
            Policy(
                key=spec["key"],
                name=spec["name"],
                description=spec.get("description"),
                category=spec.get("category"),
                enabled=True,
                priority=spec.get("priority", 100),
                parameters=spec.get("parameters", []),
                rule_text=spec.get("rule_text"),
                applies_to=spec.get("applies_to"),
                is_builtin=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return {"created": created, "total": db.query(Policy).count()}


def effective_inputs(db: Session) -> dict:
    """Current policy values, keyed by the Auto workflow input they feed.

    This is what makes a policy edit reach the agent: pass this object as the
    inputs of the next Orchestrator run and the new thresholds are in force.
    Disabled policies contribute nothing.
    """
    inputs: dict[str, Any] = {}
    provenance: dict[str, str] = {}

    policies = (
        db.query(Policy)
        .filter(Policy.enabled.is_(True))
        .order_by(Policy.priority, Policy.key)
        .all()
    )
    for policy in policies:
        for param in policy.parameters or []:
            target = param.get("maps_to_input")
            if not target:
                continue
            # Lower priority number wins a collision, and the clash is logged
            # rather than silently resolved.
            if target in inputs and provenance.get(target) != policy.key:
                log.warning(
                    "Workflow input %r is set by both %s and %s; keeping %s",
                    target,
                    provenance.get(target),
                    policy.key,
                    provenance.get(target),
                )
                continue
            inputs[target] = param.get("value")
            provenance[target] = policy.key

    return {"inputs": inputs, "provenance": provenance, "policy_count": len(policies)}


def record_change(
    db: Session,
    policy: Policy,
    field: str,
    old_value: Any,
    new_value: Any,
    changed_by: str | None,
    note: str | None = None,
) -> PolicyChange:
    """Append to the policy change trail. Called for every mutation."""

    def _fmt(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        return str(value)

    change = PolicyChange(
        policy_id=policy.id,
        policy_key=policy.key,
        field=field,
        old_value=_fmt(old_value),
        new_value=_fmt(new_value),
        changed_by=changed_by,
        note=note,
    )
    db.add(change)
    return change


# ---------------------------------------------------------------------------
# Ingesting evaluations that Operators reported
# ---------------------------------------------------------------------------

EVALUATION_COLLECTION_KEYS = (
    "policy_evaluations",
    "policy_evaluation_log",
    "policy_checks",
    "evaluations",
    "verdicts",
)

EVAL_ALIASES: dict[str, tuple[str, ...]] = {
    "policy_key": ("policy_key", "policy", "policy_id", "rule", "rule_key", "policy_name"),
    "policy_name": ("policy_name", "policy_label", "name", "rule_name"),
    "subject_ref": (
        "subject_ref",
        "issue_key",
        "ticket_key",
        "ticket",
        "subject",
        "cluster_key",
        "change_key",
        "key",
    ),
    "subject_type": ("subject_type", "entity_type", "type"),
    "outcome": ("outcome", "result", "status", "passed", "state"),
    "decision": ("decision", "verdict", "action", "route"),
    "reason": ("reason", "rationale", "explanation", "message", "detail", "why"),
    "threshold": (
        "threshold_in_force",
        "threshold",
        "thresholds",
        "parameter_values",
        "policy_values",
        "settings",
    ),
    "observed": (
        "observed_values",
        "observed",
        "inputs",
        "values",
        "evidence",
        "compared",
    ),
    "evaluated_at": ("evaluated_at", "timestamp", "time", "at"),
}


# Operators often nest the policy detail one level down rather than putting it
# beside the subject. Both shapes are valid; these are the containers seen so
# far, and an unknown one simply yields nothing rather than breaking.
NESTED_DETAIL_KEYS = ("verdict_data", "policy", "policy_detail", "details", "evaluation")


def _flatten(payload: dict) -> dict:
    """Merge a nested policy-detail object up to the top level.

    The nested values win: when a verdict carries both a subject-level `state`
    and a `verdict_data.policy_key`, the latter is the more specific statement
    of which rule fired.
    """
    merged = dict(payload)
    for key in NESTED_DETAIL_KEYS:
        nested = payload.get(key)
        if isinstance(nested, dict):
            merged.update({k: v for k, v in nested.items() if v is not None})
    return merged


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


def _normalise_outcome(value: Any) -> str | None:
    """Map whatever the agent said onto pass / fail / block / escalate."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "pass" if value else "fail"
    text = str(value).strip().lower()
    if text in ("true", "pass", "passed", "ok", "allow", "allowed", "cleared", "success"):
        return "pass"
    if text in ("false", "fail", "failed", "deny", "denied", "violation"):
        return "fail"
    if text.startswith("block"):
        return "block"
    if "review" in text or "escalat" in text or "approval" in text:
        return "escalate"
    return text[:32] or None


def _parse_output(outputs: Any) -> Any:
    """Same envelope as the Elimination extractor: JSON string under `output`."""
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


def _find_eval_collections(node: Any, depth: int = 0) -> list[list]:
    found: list[list] = []
    if depth > 6:
        return found
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                str(key).lower() in EVALUATION_COLLECTION_KEYS
                and isinstance(value, list)
                and value
                and all(isinstance(i, dict) for i in value)
            ):
                found.append(value)
            else:
                found.extend(_find_eval_collections(value, depth + 1))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_eval_collections(item, depth + 1))
    return found


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def ingest_evaluations(db: Session) -> dict:
    """Mirror policy evaluations out of mirrored agent activity.

    Idempotent: an evaluation already recorded for the same activity, policy and
    subject is skipped, so this is safe to call on every sync.
    """
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )

    known_policies = {p.key: p.name for p in db.query(Policy).all()}
    created = skipped = 0

    for activity, run in rows:
        # Evaluations may be inline or inside a downloaded JSON report.
        payloads = [_parse_output(activity.outputs)]
        if activity.artifact_data:
            payloads.extend(activity.artifact_data.values())

        collections: list[list] = []
        for payload in payloads:
            if payload is not None:
                collections.extend(_find_eval_collections(payload))

        for collection in collections:
            for entry in collection:
                # Flatten any nested policy-detail object before reading fields.
                raw = _flatten(entry)
                policy_key = _first(raw, EVAL_ALIASES["policy_key"])
                policy_key = str(policy_key).strip() if policy_key else None
                subject = _first(raw, EVAL_ALIASES["subject_ref"])
                subject = str(subject).strip() if subject else None

                if not policy_key and not subject:
                    continue

                exists = (
                    db.query(PolicyEvaluation)
                    .filter(
                        PolicyEvaluation.activity_id == activity.id,
                        PolicyEvaluation.policy_key == policy_key,
                        PolicyEvaluation.subject_ref == subject,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    continue

                name = _first(raw, EVAL_ALIASES["policy_name"])
                db.add(
                    PolicyEvaluation(
                        policy_key=policy_key,
                        policy_name=(
                            str(name)
                            if name
                            else known_policies.get(policy_key or "", None)
                        ),
                        subject_ref=subject,
                        subject_type=(
                            str(_first(raw, EVAL_ALIASES["subject_type"]))
                            if _first(raw, EVAL_ALIASES["subject_type"])
                            else None
                        ),
                        outcome=_normalise_outcome(_first(raw, EVAL_ALIASES["outcome"])),
                        decision=(
                            str(_first(raw, EVAL_ALIASES["decision"]))[:64]
                            if _first(raw, EVAL_ALIASES["decision"])
                            else None
                        ),
                        reason=(
                            str(_first(raw, EVAL_ALIASES["reason"]))
                            if _first(raw, EVAL_ALIASES["reason"])
                            else None
                        ),
                        threshold_in_force=_first(raw, EVAL_ALIASES["threshold"]),
                        observed_values=_first(raw, EVAL_ALIASES["observed"]),
                        auto_run_id=run.auto_run_id,
                        workflow_name=run.workflow_name,
                        step_name=activity.step_name,
                        activity_id=activity.id,
                        source="agent",
                        evaluated_at=_parse_dt(
                            _first(raw, EVAL_ALIASES["evaluated_at"])
                        )
                        or activity.completed_at
                        or run.auto_created_at,
                        raw_payload=entry,
                    )
                )
                created += 1

    if created:
        db.commit()

    total = db.query(PolicyEvaluation).count()
    result = {"created": created, "already_recorded": skipped, "total": total}
    if total == 0:
        result["note"] = (
            "No Operator has reported a policy evaluation yet. Operators must "
            "emit a policy_evaluations array for these to appear."
        )
    return result


def evaluation_summary(db: Session) -> dict:
    """Counts per policy and per outcome, for the Policies page header."""
    evaluations = db.query(PolicyEvaluation).all()
    by_policy: dict[str, dict] = {}
    by_outcome: dict[str, int] = {}

    for ev in evaluations:
        key = ev.policy_key or "unattributed"
        entry = by_policy.setdefault(
            key,
            {"policy_key": key, "policy_name": ev.policy_name, "total": 0, "outcomes": {}},
        )
        entry["total"] += 1
        outcome = ev.outcome or "unknown"
        entry["outcomes"][outcome] = entry["outcomes"].get(outcome, 0) + 1
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

    last = max(
        (e.evaluated_at for e in evaluations if e.evaluated_at is not None),
        default=None,
    )
    return {
        "total": len(evaluations),
        "by_outcome": by_outcome,
        "by_policy": sorted(by_policy.values(), key=lambda e: e["total"], reverse=True),
        "last_evaluated_at": last.isoformat() if last else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
