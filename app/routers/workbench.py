"""
Workbench — the human-in-the-loop queue.

Exceptions arrive from Operators on Supervity Auto with their full context
attached. A human approves, rejects, modifies or asks for more information, and
that decision is recorded against the agent's own recommendation.
"""

import logging
import re
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


# ---------------------------------------------------------------------------
# Groups — one decision covering everything the agent judged to be one problem
# ---------------------------------------------------------------------------
#
# A queue of 247 items is not 247 decisions. Most of them are the same problem
# arriving under different ticket numbers, and the Operators already said so:
# every item they clustered carries the cluster it belongs to. Grouping on that
# key lets a person decide once and have it apply to the whole class.
#
# The grouping is the agent's, not ours. Items the Operators did not cluster —
# change approvals and rollback verifications, which each concern a specific
# change — stay individual, because deciding sixty-eight separate change
# requests with one click would be a worse error than the tedium it saves.


# Filler the Operators append to cluster names — "unified", "cluster", "issues"
# — which varies between runs and split the same class into several groups.
# Stripping it is text normalisation, not clustering: two names that differ only
# by these words are the same name. Deciding that two *differently named*
# classes mean the same thing is a judgement about meaning, and that belongs to
# an Operator on Auto, so it is not done here.
_GROUP_FILLER = re.compile(r"\b(unified|cluster|class|group|incidents?|issues?)\b")
_NON_WORD = re.compile(r"[^a-z0-9]+")

# The shape of a ticket reference, used to tell a ticket apart from a cluster
# name. A format, not a value — no ticket key or project prefix is written down.
_TICKET_KEY = re.compile(r"[A-Za-z][A-Za-z0-9]*-\d+")


def _group_key(row: WorkbenchException) -> str | None:
    raw = (row.context or {}).get("cluster_key")
    if not raw:
        return None
    text = _NON_WORD.sub(" ", str(raw).lower())
    text = _GROUP_FILLER.sub("", text)
    return re.sub(r"\s+", " ", text).strip() or None


@router.get("/groups")
def list_groups(
    status: str = Query("open"),
    db: Session = Depends(get_db),
):
    """Open items gathered into the classes the Operators put them in.

    Returns the groups, plus a count of the items that carry no cluster and so
    must be decided one at a time. That count is reported rather than folded
    into a group, because a number that quietly includes something it should
    not is the failure this build argues against.
    """
    rows = db.query(WorkbenchException).filter(WorkbenchException.status == status).all()

    groups: dict[str, dict] = {}
    ungrouped = 0
    for row in rows:
        key = _group_key(row)
        if key is None:
            ungrouped += 1
            continue
        context = row.context or {}
        entry = groups.setdefault(
            key,
            {
                "group_key": key,
                "title": context.get("summary") or row.title,
                "exception_type": row.exception_type,
                "reason": row.reason,
                "affected_system": context.get("affected_system"),
                "owning_team": context.get("owning_team"),
                "proposed_fix": context.get("proposed_fix"),
                "kb_status": context.get("kb_status"),
                # What the Operator said the whole class is worth, kept separate
                # from how many items happen to be queued here.
                "class_size_reported_by_agent": context.get("member_count"),
                "items": [],
                "tickets": [],
                "cluster_names": [],
                "workflow_name": row.workflow_name,
            },
        )
        entry["items"].append(row.id)

        # Two different things, kept apart on purpose.
        #
        # A class-level item's subject is the cluster the Operator named, not a
        # ticket, and the same class arrives under slightly different cluster
        # names on each run. Listing those under a heading like "tickets
        # covered" reads as though they were ticket keys, which they are not.
        #
        # Ticket keys appear only where an Operator actually listed them. Most
        # classes report a member count and no members, and that gap is stated
        # rather than filled with the nearest available strings.
        ref = row.subject_ref
        if ref and _TICKET_KEY.fullmatch(str(ref)):
            if ref not in entry["tickets"]:
                entry["tickets"].append(ref)
        elif ref and ref not in entry["cluster_names"]:
            entry["cluster_names"].append(ref)

        members = context.get("member_keys")
        if isinstance(members, str):
            members = re.findall(r"[A-Za-z][A-Za-z0-9]*-\d+", members)
        if isinstance(members, list):
            for member in members:
                if str(member) not in entry["tickets"]:
                    entry["tickets"].append(str(member))

    ordered = sorted(groups.values(), key=lambda g: len(g["items"]), reverse=True)
    for group in ordered:
        group["item_count"] = len(group["items"])
        # Whether the Operators named the tickets in this class or only counted
        # them. The UI says which, so nobody reads a class size as a ticket list.
        group["tickets_listed_by_agent"] = len(group["tickets"]) > 0

    return {
        "groups": ordered,
        "group_count": len(ordered),
        "items_in_groups": sum(g["item_count"] for g in ordered),
        # Change approvals and rollback verifications concern one specific
        # change each. The Operators did not cluster them, so neither do we.
        "ungrouped_items": ungrouped,
        "ungrouped_note": (
            "These carry no cluster from any Operator — each concerns a specific "
            "change or verification and is decided on its own."
        ),
        "status": status,
    }


@router.post("/groups/{group_key}/resolve")
def resolve_group(
    group_key: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Apply one decision to every open item in a class.

    Each item is still written individually, with the same note and a record
    that it was decided as part of a group — so the audit trail shows what a
    person actually saw when they decided, not a single row standing in for
    many.
    """
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

    rows = [
        row
        for row in db.query(WorkbenchException)
        .filter(WorkbenchException.status == "open")
        .all()
        if _group_key(row) == group_key
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="No open items in that group")

    actor = _actor(user)
    now = datetime.now(timezone.utc)
    group_note = f"Decided as part of the class '{group_key}' ({len(rows)} items)."
    for row in rows:
        row.resolution = resolution
        row.resolution_note = f"{note}\n\n{group_note}" if note else group_note
        row.resolved_by = actor
        row.resolved_at = now
        row.status = "open" if resolution == "more_info" else "resolved"

    db.commit()
    log.info(
        "Workbench group %s resolved as %s across %d items by %s",
        group_key,
        resolution,
        len(rows),
        actor,
    )
    return {
        "group_key": group_key,
        "resolution": resolution,
        "items_decided": len(rows),
        "tickets": [r.subject_ref for r in rows if r.subject_ref],
        "resolved_by": actor,
        "resolved_at": now.isoformat(),
    }


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
