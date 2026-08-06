"""
AI Policies — editable governance rules and their audit trail.

Policies are stored and edited here; they are enforced by Operators on
Supervity Auto, which read the current values as workflow inputs. That is what
makes an edit on this page change what the agent does on its next run without
anyone touching a workflow.
"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.policy import Policy, PolicyChange, PolicyEvaluation
from ..security import get_current_user
from ..services import policy as policy_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/policies", tags=["Policies"])


def _actor(user: dict | None) -> str:
    """Best available identity for the audit trail."""
    if not user:
        return "unknown"
    return (
        user.get("email")
        or user.get("preferred_username")
        or user.get("name")
        or user.get("sub")
        or "unknown"
    )


def _policy_out(p: Policy) -> dict:
    return {
        "id": p.id,
        "key": p.key,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "enabled": p.enabled,
        "priority": p.priority,
        "parameters": p.parameters or [],
        "rule_text": p.rule_text,
        "applies_to": p.applies_to or [],
        "is_builtin": p.is_builtin,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "updated_by": p.updated_by,
    }


def _change_out(c: PolicyChange) -> dict:
    return {
        "id": c.id,
        "policy_key": c.policy_key,
        "field": c.field,
        "old_value": c.old_value,
        "new_value": c.new_value,
        "changed_by": c.changed_by,
        "note": c.note,
        "changed_at": c.changed_at.isoformat() if c.changed_at else None,
    }


def _evaluation_out(e: PolicyEvaluation) -> dict:
    return {
        "id": e.id,
        "policy_key": e.policy_key,
        "policy_name": e.policy_name,
        "subject_ref": e.subject_ref,
        "subject_type": e.subject_type,
        "outcome": e.outcome,
        "decision": e.decision,
        "reason": e.reason,
        "threshold_in_force": e.threshold_in_force,
        "observed_values": e.observed_values,
        "auto_run_id": e.auto_run_id,
        "workflow_name": e.workflow_name,
        "step_name": e.step_name,
        "source": e.source,
        "evaluated_at": e.evaluated_at.isoformat() if e.evaluated_at else None,
    }


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


@router.get("")
def list_policies(db: Session = Depends(get_db)):
    """All policies, highest precedence first. Seeds the built-ins on first call."""
    policy_service.seed_builtin_policies(db)
    rows = db.query(Policy).order_by(Policy.priority, Policy.key).all()
    return {
        "policies": [_policy_out(p) for p in rows],
        "count": len(rows),
        "active_count": sum(1 for p in rows if p.enabled),
    }


@router.get("/effective-inputs")
def get_effective_inputs(db: Session = Depends(get_db)):
    """Current policy values keyed by the Auto workflow input each one feeds.

    Pass this as the inputs of the next Orchestrator run and the edited
    thresholds take effect. Disabled policies contribute nothing.
    """
    policy_service.seed_builtin_policies(db)
    return policy_service.effective_inputs(db)


@router.get("/changes")
def list_changes(
    policy_key: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Who changed which policy value, and when."""
    q = db.query(PolicyChange)
    if policy_key:
        q = q.filter(PolicyChange.policy_key == policy_key)
    rows = q.order_by(PolicyChange.changed_at.desc()).limit(limit).all()
    return {"changes": [_change_out(c) for c in rows], "count": len(rows)}


@router.get("/{key}")
def get_policy(key: str, db: Session = Depends(get_db)):
    row = db.query(Policy).filter_by(key=key).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No policy with key '{key}'")
    return _policy_out(row)


@router.patch("/{key}")
def update_policy(
    key: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Edit a policy without touching code.

    Accepts `enabled`, `priority`, `rule_text`, `description`, and
    `parameters` as a {name: value} map. Every accepted change is written to
    the change trail before it is applied.
    """
    row = db.query(Policy).filter_by(key=key).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No policy with key '{key}'")

    actor = _actor(user)
    note = payload.get("note")
    changed: list[str] = []
    rejected: list[dict] = []

    for field in ("enabled", "priority", "rule_text", "description", "name"):
        if field not in payload:
            continue
        new_value = payload[field]
        old_value = getattr(row, field)
        if new_value == old_value:
            continue
        policy_service.record_change(db, row, field, old_value, new_value, actor, note)
        setattr(row, field, new_value)
        changed.append(field)

    param_updates: dict[str, Any] = payload.get("parameters") or {}
    if param_updates:
        params = [dict(p) for p in (row.parameters or [])]
        known = {p.get("name") for p in params}

        for name, new_value in param_updates.items():
            if name not in known:
                rejected.append({"parameter": name, "reason": "no such parameter"})
                continue

            for param in params:
                if param.get("name") != name:
                    continue

                coerced, error = _coerce_parameter(param, new_value)
                if error:
                    rejected.append({"parameter": name, "reason": error})
                    break

                old_value = param.get("value")
                if coerced == old_value:
                    break

                policy_service.record_change(
                    db, row, f"parameters.{name}", old_value, coerced, actor, note
                )
                param["value"] = coerced
                changed.append(f"parameters.{name}")
                break

        row.parameters = params

    if changed:
        row.updated_by = actor
        db.commit()
        db.refresh(row)
    elif rejected:
        db.rollback()

    return {
        "policy": _policy_out(row),
        "changed": changed,
        # Bad values are reported, never silently clamped into range — an
        # operator must know their edit did not take effect.
        "rejected": rejected,
    }


def _coerce_parameter(param: dict, value: Any) -> tuple[Any, str | None]:
    """Validate a new parameter value against its declared type and bounds."""
    ptype = param.get("type", "string")

    if ptype == "boolean":
        if isinstance(value, bool):
            return value, None
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true", None
        return None, "expected true or false"

    if ptype == "number":
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None, "expected a number"
        minimum, maximum = param.get("min"), param.get("max")
        if minimum is not None and num < float(minimum):
            return None, f"must be at least {minimum}"
        if maximum is not None and num > float(maximum):
            return None, f"must be at most {maximum}"
        # Keep integers as integers so they render without a trailing .0
        if num.is_integer() and (param.get("step") is None or float(param["step"]) >= 1):
            return int(num), None
        return num, None

    if value is None:
        return None, "expected a value"
    return str(value), None


@router.post("/{key}/reset")
def reset_policy(
    key: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Return every parameter to its default. Logged like any other change."""
    row = db.query(Policy).filter_by(key=key).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No policy with key '{key}'")

    actor = _actor(user)
    params = [dict(p) for p in (row.parameters or [])]
    changed: list[str] = []

    for param in params:
        if "default" not in param or param.get("value") == param.get("default"):
            continue
        policy_service.record_change(
            db,
            row,
            f"parameters.{param.get('name')}",
            param.get("value"),
            param.get("default"),
            actor,
            "reset to default",
        )
        param["value"] = param["default"]
        changed.append(str(param.get("name")))

    if changed:
        row.parameters = params
        row.updated_by = actor
        db.commit()
        db.refresh(row)

    return {"policy": _policy_out(row), "reset": changed}


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------


@router.get("/evaluations/log")
def list_evaluations(
    policy_key: str | None = None,
    outcome: str | None = None,
    auto_run_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Every policy evaluation an Operator reported, newest first."""
    q = db.query(PolicyEvaluation)
    if policy_key:
        q = q.filter(PolicyEvaluation.policy_key == policy_key)
    if outcome:
        q = q.filter(PolicyEvaluation.outcome == outcome)
    if auto_run_id:
        q = q.filter(PolicyEvaluation.auto_run_id == auto_run_id)

    total = q.count()
    rows = (
        q.order_by(PolicyEvaluation.evaluated_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "evaluations": [_evaluation_out(e) for e in rows],
        "count": len(rows),
        "total": total,
    }


@router.get("/evaluations/summary")
def evaluations_summary(db: Session = Depends(get_db)):
    """Counts per policy and per outcome for the Policies page header."""
    return policy_service.evaluation_summary(db)


@router.post("/evaluations/ingest")
def ingest_evaluations(db: Session = Depends(get_db)):
    """Pull policy evaluations out of mirrored agent activity.

    Safe to call repeatedly — already-recorded evaluations are skipped.
    """
    return policy_service.ingest_evaluations(db)
