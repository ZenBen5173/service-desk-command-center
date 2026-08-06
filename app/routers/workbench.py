"""
Workbench — the human-in-the-loop queue.

Exceptions arrive from Operators on Supervity Auto with their full context
attached. A human approves, rejects, modifies or asks for more information, and
that decision is recorded against the agent's own recommendation.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.workbench import WorkbenchException
from ..security import get_current_user
from ..services import workbench as workbench_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["Workbench"])

VALID_RESOLUTIONS = {"approve", "reject", "modify", "more_info"}


def _actor(user: dict | None) -> str:
    if not user:
        return "unknown"
    return (
        user.get("email")
        or user.get("preferred_username")
        or user.get("name")
        or user.get("sub")
        or "unknown"
    )


def _out(e: WorkbenchException) -> dict:
    return {
        "id": e.id,
        "dedupe_key": e.dedupe_key,
        "exception_type": e.exception_type,
        "title": e.title,
        "subject_ref": e.subject_ref,
        "subject_type": e.subject_type,
        "reason": e.reason,
        "agent_recommendation": e.agent_recommendation,
        "agent_confidence": e.agent_confidence,
        "context": e.context,
        "priority": e.priority,
        "auto_run_id": e.auto_run_id,
        "workflow_name": e.workflow_name,
        "step_name": e.step_name,
        "status": e.status,
        "resolution": e.resolution,
        "resolution_note": e.resolution_note,
        "resolved_by": e.resolved_by,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        "raised_at": e.raised_at.isoformat() if e.raised_at else None,
    }


@router.get("/exceptions")
def list_exceptions(
    status: str | None = Query(None, description="open | resolved"),
    exception_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """The queue. Open items first, then most recently raised."""
    q = db.query(WorkbenchException)
    if status == "open":
        q = q.filter(WorkbenchException.status == "open")
    elif status == "resolved":
        q = q.filter(WorkbenchException.status != "open")
    if exception_type:
        q = q.filter(WorkbenchException.exception_type == exception_type)

    total = q.count()
    rows = (
        q.order_by(
            # Open work outranks decided work regardless of age.
            (WorkbenchException.status != "open"),
            WorkbenchException.raised_at.desc().nullslast(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "exceptions": [_out(e) for e in rows],
        "count": len(rows),
        "total": total,
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Queue counts for the Workbench header."""
    return workbench_service.queue_summary(db)


@router.post("/ingest")
def ingest(db: Session = Depends(get_db)):
    """Pull escalations out of mirrored agent activity into the queue."""
    return workbench_service.ingest_exceptions(db)


@router.get("/exceptions/{exception_id}")
def get_exception(exception_id: int, db: Session = Depends(get_db)):
    row = db.query(WorkbenchException).filter_by(id=exception_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    return _out(row)


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(
    exception_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Record a human decision on one exception.

    `more_info` deliberately leaves the item open — asking a question is not a
    decision, and closing it would lose the work.
    """
    row = db.query(WorkbenchException).filter_by(id=exception_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    resolution = str(payload.get("resolution", "")).strip().lower()
    if resolution not in VALID_RESOLUTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"resolution must be one of {sorted(VALID_RESOLUTIONS)}",
        )

    note = payload.get("note")
    if resolution == "modify" and not note:
        raise HTTPException(
            status_code=400,
            detail="A note is required when modifying the agent's recommendation, "
            "so the change is on the record.",
        )

    actor = _actor(user)
    row.resolution = resolution
    row.resolution_note = note
    row.resolved_by = actor
    row.resolved_at = datetime.now(timezone.utc)
    row.status = "open" if resolution == "more_info" else "resolved"

    db.commit()
    db.refresh(row)

    log.info(
        "Workbench exception %s resolved as %s by %s", exception_id, resolution, actor
    )
    return _out(row)


@router.post("/exceptions/{exception_id}/reopen")
def reopen_exception(
    exception_id: int,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Undo a decision. The previous resolution stays visible in the note."""
    row = db.query(WorkbenchException).filter_by(id=exception_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    previous = row.resolution
    note = payload.get("note")
    row.status = "open"
    row.resolution = None
    row.resolution_note = (
        f"Reopened by {_actor(user)}"
        + (f": {note}" if note else "")
        + (f" (was {previous})" if previous else "")
    )
    row.resolved_by = None
    row.resolved_at = None
    db.commit()
    db.refresh(row)
    return _out(row)
