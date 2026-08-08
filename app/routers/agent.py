"""
Live agent activity from Supervity Auto.

These endpoints back the Command Center's real numbers. Everything returned here
traces to a run that actually happened on Auto — nothing is generated, estimated
or defaulted. When Auto cannot be reached, the endpoints say so rather than
falling back to plausible-looking figures.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.agent import AgentActivity, AgentRun, AgentWorkflow
from ..services import agent_sync, resolution
from ..services.supervity import (
    SupervityClient,
    SupervityError,
    SupervityNotConfigured,
    get_supervity_client,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["Agent"])


# ---------------------------------------------------------------------------
# Serialisers — keep the wire shape stable and camel-free for the frontend
# ---------------------------------------------------------------------------


def _workflow_out(w: AgentWorkflow) -> dict:
    return {
        "id": w.id,
        "auto_id": w.auto_id,
        "name": w.name,
        "description": w.description,
        "services": w.services or [],
        "role": w.role,
        "auto_updated_at": w.auto_updated_at.isoformat() if w.auto_updated_at else None,
        "synced_at": w.synced_at.isoformat() if w.synced_at else None,
    }


def _resolve_run_name(r: AgentRun, names_by_auto_id: dict[str, str]) -> str:
    """Best available name for a run.

    Auto omits workflowName on some runs. Fall back to the mirrored workflow
    list, then say plainly that the workflow is gone rather than showing a bare
    UUID or the word "Unnamed", which reads like a bug.
    """
    if r.workflow_name:
        return r.workflow_name
    if r.auto_workflow_id and r.auto_workflow_id in names_by_auto_id:
        return names_by_auto_id[r.auto_workflow_id]
    if r.auto_workflow_id:
        return f"Deleted workflow ({r.auto_workflow_id[:8]}...)"
    return "Unknown workflow"


def _run_out(r: AgentRun, names_by_auto_id: dict[str, str] | None = None) -> dict:
    return {
        "id": r.id,
        "auto_run_id": r.auto_run_id,
        "auto_workflow_id": r.auto_workflow_id,
        "workflow_name": _resolve_run_name(r, names_by_auto_id or {}),
        "status": r.status,
        "inputs": r.inputs,
        "started_at": r.auto_created_at.isoformat() if r.auto_created_at else None,
        "finished_at": r.auto_updated_at.isoformat() if r.auto_updated_at else None,
        "duration_seconds": r.duration_seconds,
        "timeline_synced": r.timeline_synced_at is not None,
        "timeline_error": r.timeline_error,
    }


def _activity_out(a: AgentActivity) -> dict:
    return {
        "id": a.id,
        "auto_activity_id": a.auto_activity_id,
        "sequence": a.sequence,
        "step_id": a.step_id,
        "step_name": a.step_name,
        "step_description": a.step_description,
        "status": a.status,
        "kind": a.kind,
        "attempt": a.attempt,
        "outputs": a.outputs,
        "error_details": a.error_details,
        "started_at": a.started_at.isoformat() if a.started_at else None,
        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        "duration_seconds": a.duration_seconds,
    }


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------


@router.get("/status")
async def agent_status(
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """Is Auto configured and reachable, and what have we mirrored so far?"""
    health = await client.health()

    workflows = db.query(AgentWorkflow).all()
    return {
        "configured": client.is_configured,
        "base_url": client.base_url,
        "healthy": health.get("healthy", False),
        "detail": health.get("detail"),
        "mirrored": {
            "workflows": len(workflows),
            "orchestrators": sum(1 for w in workflows if w.role == "orchestrator"),
            "operators": sum(1 for w in workflows if w.role == "operator"),
            "runs": db.query(AgentRun).count(),
            "activities": db.query(AgentActivity).count(),
        },
    }


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


@router.post("/sync")
async def sync_from_auto(
    timeline_limit: int = Query(25, ge=0, le=200),
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """Refresh workflows, runs and the newest activity timelines from Auto."""
    try:
        return await agent_sync.sync_all(db, client, timeline_limit=timeline_limit)
    except SupervityNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SupervityError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/workflows")
def list_workflows(role: str | None = None, db: Session = Depends(get_db)):
    """The Orchestrator and Operators as mirrored from Auto."""
    q = db.query(AgentWorkflow)
    if role:
        q = q.filter(AgentWorkflow.role == role)
    rows = q.order_by(AgentWorkflow.role, AgentWorkflow.name).all()
    return {"workflows": [_workflow_out(w) for w in rows], "count": len(rows)}


@router.get("/runs")
def list_runs(
    workflow_id: str | None = Query(None, description="Auto workflow id"),
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Recent runs, newest first."""
    q = db.query(AgentRun)
    if workflow_id:
        q = q.filter(AgentRun.auto_workflow_id == workflow_id)
    if status:
        q = q.filter(AgentRun.status == status)
    total = q.count()
    rows = (
        q.order_by(AgentRun.auto_created_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    return {
        "runs": [_run_out(r, names) for r in rows],
        "count": len(rows),
        "total": total,
    }


@router.get("/runs/{auto_run_id}")
async def get_run(
    auto_run_id: str,
    refresh: bool = Query(False, description="Re-fetch the timeline from Auto first"),
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """One run with its full activity timeline.

    The timeline is the authoritative record of what the agent did. Auto's
    natural-language summaries have been observed contradicting it, so the UI
    should render these step outputs rather than any prose.
    """
    row = db.query(AgentRun).filter_by(auto_run_id=auto_run_id).first()

    if refresh or row is None or row.timeline_synced_at is None:
        try:
            await agent_sync.sync_run_timeline(db, client, auto_run_id)
            row = db.query(AgentRun).filter_by(auto_run_id=auto_run_id).first()
        except SupervityNotConfigured as exc:
            if row is None:
                raise HTTPException(status_code=503, detail=str(exc))
        except SupervityError as exc:
            if row is None:
                raise HTTPException(status_code=502, detail=str(exc))
            log.warning("Timeline refresh failed for %s: %s", auto_run_id, exc)

    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    activities = (
        db.query(AgentActivity)
        .filter(AgentActivity.run_id == row.id)
        .order_by(AgentActivity.sequence)
        .all()
    )
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    return {
        "run": _run_out(row, names),
        "activities": [_activity_out(a) for a in activities],
        "activity_count": len(activities),
    }


# ---------------------------------------------------------------------------
# Dashboard metrics — real numbers only
# ---------------------------------------------------------------------------


@router.get("/metrics")
def agent_metrics(db: Session = Depends(get_db)):
    """Headline figures for the Command Center.

    Every value is computed from mirrored runs. If nothing has been synced yet,
    the counts are zero and `has_data` is false — the UI must show that state
    rather than a placeholder number.
    """
    all_runs = db.query(AgentRun).all()
    workflows = db.query(AgentWorkflow).all()

    # Count only runs belonging to a workflow that still exists on Auto. The
    # mirror keeps runs from workflows since deleted — earlier rounds, discarded
    # experiments — and attributing those to the current agent roster overstates
    # it. They are reported separately rather than silently dropped, because a
    # figure that quietly excludes something is the failure this whole build
    # argues against.
    live_ids = {w.auto_id for w in workflows}
    runs = [r for r in all_runs if r.auto_workflow_id in live_ids]
    retired_runs = len(all_runs) - len(runs)

    total = len(runs)
    completed = [r for r in runs if (r.status or "").lower() == "completed"]
    failed = [r for r in runs if (r.status or "").lower() in ("failed", "error")]
    running = [r for r in runs if (r.status or "").lower() in ("running", "in_progress")]

    durations = [r.duration_seconds for r in completed if r.duration_seconds is not None]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else None

    finished = len(completed) + len(failed)
    success_rate = round(100.0 * len(completed) / finished, 1) if finished else None

    last_run = max(
        (r.auto_created_at for r in runs if r.auto_created_at is not None), default=None
    )

    # Per-workflow breakdown so the UI can show which Operator is doing the work.
    # Auto omits workflowName on some runs — usually ones whose workflow has since
    # been deleted or renamed. Resolve through the mirrored workflow list first,
    # and label the rest honestly rather than printing a bare UUID.
    names_by_auto_id = {w.auto_id: w.name for w in workflows}
    by_workflow: dict[str, dict] = {}
    for r in runs:
        key = _resolve_run_name(r, names_by_auto_id)
        entry = by_workflow.setdefault(
            key, {"workflow_name": key, "runs": 0, "completed": 0, "failed": 0}
        )
        entry["runs"] += 1
        status = (r.status or "").lower()
        if status == "completed":
            entry["completed"] += 1
        elif status in ("failed", "error"):
            entry["failed"] += 1

    return {
        "has_data": total > 0,
        "total_runs": total,
        # Runs whose workflow no longer exists on Auto, excluded from every
        # figure above and surfaced so the exclusion is visible.
        "retired_workflow_runs": retired_runs,
        "completed_runs": len(completed),
        "failed_runs": len(failed),
        "running_runs": len(running),
        "success_rate_pct": success_rate,
        "avg_duration_seconds": avg_duration,
        "last_run_at": last_run.isoformat() if last_run else None,
        "operator_count": sum(1 for w in workflows if w.role == "operator"),
        "orchestrator_count": sum(1 for w in workflows if w.role == "orchestrator"),
        "by_workflow": sorted(
            by_workflow.values(), key=lambda e: e["runs"], reverse=True
        ),
    }


# ---------------------------------------------------------------------------
# Auto-resolution
# ---------------------------------------------------------------------------


@router.get("/resolution")
def resolution_summary(db: Session = Depends(get_db)):
    """Per-ticket verdicts the evidence Operator produced, and the rate they imply.

    Read-only. Returns whatever decisions have been mirrored so far; an empty
    list means the Operator has not been asked about any ticket individually,
    not that it decided nothing.
    """
    return resolution.read_decisions(db)


@router.post("/resolution/sweep")
async def resolution_sweep(
    limit: int = Query(20, ge=1, le=100),
    concurrency: int = Query(3, ge=1, le=5),
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """Ask the evidence Operator about each pending ticket, one call per ticket.

    Blocking, and slow by design — every ticket is a real Operator run on Auto.
    Twenty tickets take a few minutes.
    """
    try:
        return await resolution.sweep(db, client, limit=limit, concurrency=concurrency)
    except SupervityNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SupervityError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Triggering
# ---------------------------------------------------------------------------


@router.post("/workflows/{auto_workflow_id}/execute")
async def execute_workflow(
    auto_workflow_id: str,
    inputs: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """Run an Auto workflow and mirror the result.

    Blocking — Auto runs these for minutes, so callers should expect to wait.
    """
    try:
        result = await client.execute(auto_workflow_id, inputs=inputs or None)
    except SupervityNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except SupervityError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Mirror it straight away so the Command Center reflects the run.
    run_id = None
    if isinstance(result, dict):
        run_id = result.get("id") or (result.get("workflowRun") or {}).get("id")
    if run_id:
        try:
            await agent_sync.sync_run_timeline(db, client, run_id)
        except SupervityError as exc:
            log.warning("Could not mirror run %s after execute: %s", run_id, exc)

    return {"auto_run_id": run_id, "result": result}
