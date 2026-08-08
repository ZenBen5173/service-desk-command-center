"""
Pull agent activity from Supervity Auto into the local mirror.

Read-only against Auto. Idempotent: syncing twice updates rows rather than
duplicating them, so it is safe to call from a refresh button during a demo.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun, AgentWorkflow
from .supervity import SupervityClient, SupervityError

log = logging.getLogger(__name__)


def _parse_dt(value) -> datetime | None:
    """Parse Auto's ISO-8601 timestamps. Returns None rather than guessing."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        log.warning("Unparseable timestamp from Auto: %r", value)
        return None


def _duration(start, end) -> int | None:
    if not start or not end:
        return None
    delta = (end - start).total_seconds()
    return int(delta) if delta >= 0 else None


def _infer_role(name: str | None, description: str | None) -> str:
    """Classify a workflow as orchestrator or operator.

    Inferred from how the workflow describes itself, not from a hardcoded list of
    names — the same code has to work when workflows get renamed or added.
    """
    haystack = f"{name or ''} {description or ''}".lower()
    orchestrator_signals = ("orchestrator", "manager workflow", "coordinates")
    if any(signal in haystack for signal in orchestrator_signals):
        return "orchestrator"
    return "operator"


async def sync_workflows(db: Session, client: SupervityClient) -> dict:
    """Mirror the workflow list. Returns a summary of what changed."""
    workflows = await client.list_workflows(limit=100)
    created = updated = 0

    for wf in workflows:
        auto_id = wf.get("id")
        if not auto_id:
            continue

        row = db.query(AgentWorkflow).filter_by(auto_id=auto_id).first()
        if row is None:
            row = AgentWorkflow(auto_id=auto_id)
            db.add(row)
            created += 1
        else:
            updated += 1

        row.name = wf.get("name") or auto_id
        row.description = wf.get("description")
        row.services = wf.get("services") or []
        row.role = _infer_role(wf.get("name"), wf.get("description"))
        row.auto_created_at = _parse_dt(wf.get("createdAt"))
        row.auto_updated_at = _parse_dt(wf.get("updatedAt"))
        row.raw_payload = wf
        row.synced_at = datetime.now(timezone.utc)

    # Drop workflows that no longer exist on Auto. Deleting a duplicate or a
    # scratch workflow there must not leave it inflating the Operator count
    # here — that count is a hackathon requirement and has to be truthful.
    #
    # Runs are kept: they carry their own auto_workflow_id and workflow_name, so
    # the history of a deleted workflow stays readable. Only the foreign key is
    # released.
    seen_ids = {wf.get("id") for wf in workflows if wf.get("id")}
    removed = 0
    if seen_ids:
        stale = db.query(AgentWorkflow).filter(~AgentWorkflow.auto_id.in_(seen_ids)).all()
        for row in stale:
            db.query(AgentRun).filter(AgentRun.workflow_id == row.id).update(
                {AgentRun.workflow_id: None}, synchronize_session=False
            )
            db.delete(row)
            removed += 1

    db.commit()
    return {
        "workflows_seen": len(workflows),
        "created": created,
        "updated": updated,
        "removed_no_longer_on_auto": removed,
    }


async def sync_runs(db: Session, client: SupervityClient, limit: int = 100) -> dict:
    """Mirror recent runs across all workflows."""
    runs, _pagination = await client.list_runs(limit=limit)
    created = updated = 0

    # Map Auto workflow ids to local rows once, rather than querying per run.
    wf_rows = {w.auto_id: w.id for w in db.query(AgentWorkflow).all()}

    for run in runs:
        auto_run_id = run.get("id")
        if not auto_run_id:
            continue

        row = db.query(AgentRun).filter_by(auto_run_id=auto_run_id).first()
        if row is None:
            row = AgentRun(auto_run_id=auto_run_id)
            db.add(row)
            created += 1
        else:
            updated += 1

        auto_wf_id = run.get("workflowId")
        started = _parse_dt(run.get("createdAt"))
        ended = _parse_dt(run.get("updatedAt"))

        row.auto_workflow_id = auto_wf_id
        row.workflow_id = wf_rows.get(auto_wf_id)
        row.workflow_name = run.get("workflowName")
        row.status = run.get("status")
        row.inputs = run.get("inputs")
        row.auto_created_at = started
        row.auto_updated_at = ended
        row.duration_seconds = _duration(started, ended)
        row.raw_payload = run
        row.synced_at = datetime.now(timezone.utc)

    db.commit()
    return {"runs_seen": len(runs), "created": created, "updated": updated}


async def sync_run_timeline(db: Session, client: SupervityClient, auto_run_id: str) -> dict:
    """Fetch one run's activity timeline — the authoritative step record."""
    try:
        payload = await client.get_run(auto_run_id)
    except SupervityError as exc:
        # Auto lists runs whose timelines it no longer serves. Record that on the
        # run so the next sync skips it, and surface it rather than hiding it.
        if "404" in str(exc):
            row = db.query(AgentRun).filter_by(auto_run_id=auto_run_id).first()
            if row is not None:
                row.timeline_synced_at = datetime.now(timezone.utc)
                row.timeline_error = "Auto no longer serves a timeline for this run (404)"
                db.commit()
            return {
                "run_id": auto_run_id,
                "activities_seen": 0,
                "created": 0,
                "updated": 0,
                "unavailable": True,
            }
        raise

    run_data = payload.get("workflowRun") or {}
    activities = payload.get("activityRuns") or []

    row = db.query(AgentRun).filter_by(auto_run_id=auto_run_id).first()
    if row is None:
        # Populate the non-null columns before flushing. A run triggered from
        # here is newer than the last run-list sync, so it has no row yet, and
        # flushing an empty one fails on auto_workflow_id.
        row = AgentRun(
            auto_run_id=auto_run_id,
            auto_workflow_id=run_data.get("workflowId") or "unknown",
        )
        db.add(row)
        db.flush()

    started = _parse_dt(run_data.get("createdAt"))
    ended = _parse_dt(run_data.get("updatedAt"))
    row.auto_workflow_id = run_data.get("workflowId") or row.auto_workflow_id
    row.workflow_name = run_data.get("workflowName") or row.workflow_name
    row.status = run_data.get("status") or row.status
    row.inputs = run_data.get("inputs") if run_data.get("inputs") is not None else row.inputs
    row.auto_created_at = started or row.auto_created_at
    row.auto_updated_at = ended or row.auto_updated_at
    row.duration_seconds = _duration(row.auto_created_at, row.auto_updated_at)
    row.raw_payload = run_data or row.raw_payload
    row.timeline_synced_at = datetime.now(timezone.utc)
    db.flush()

    created = updated = 0
    for index, act in enumerate(activities):
        auto_activity_id = act.get("id")
        if not auto_activity_id:
            continue

        arow = db.query(AgentActivity).filter_by(auto_activity_id=auto_activity_id).first()
        if arow is None:
            arow = AgentActivity(auto_activity_id=auto_activity_id, run_id=row.id)
            db.add(arow)
            created += 1
        else:
            updated += 1

        a_start = _parse_dt(act.get("startedAt")) or _parse_dt(act.get("createdAt"))
        a_end = _parse_dt(act.get("completedAt")) or _parse_dt(act.get("updatedAt"))

        arow.run_id = row.id
        arow.step_id = act.get("stepId")
        arow.step_name = act.get("stepName")
        arow.step_description = act.get("stepDescription")
        arow.status = act.get("status")
        arow.kind = act.get("kind")
        arow.attempt = act.get("attempt")
        arow.outputs = act.get("outputs")

        # A step's real report is often a file rather than inline output. The
        # signed URLs expire, so download JSON reports now and keep the content.
        output_files = act.get("outputFiles") or []
        arow.output_files = output_files
        if output_files and arow.artifact_data is None:
            fetched: dict[str, object] = {}
            for f in output_files:
                url, name = f.get("url"), f.get("name") or "artifact"
                if not url or not str(name).lower().endswith(".json"):
                    continue
                data = await client.fetch_artifact(url)
                if data is not None:
                    fetched[str(name)] = data
            if fetched:
                arow.artifact_data = fetched

        err = act.get("errorDetails")
        arow.error_details = None if err is None else str(err)
        arow.started_at = a_start
        arow.completed_at = a_end
        arow.duration_seconds = _duration(a_start, a_end)
        arow.sequence = index
        arow.raw_payload = act
        arow.synced_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "run_id": auto_run_id,
        "activities_seen": len(activities),
        "created": created,
        "updated": updated,
    }


async def sync_all(db: Session, client: SupervityClient, timeline_limit: int = 25) -> dict:
    """Full refresh: workflows, recent runs, and the newest timelines.

    Timelines cost one request each, so only the most recent runs are fetched.
    Whatever is skipped is reported rather than silently dropped.
    """
    result: dict = {"errors": []}

    try:
        result["workflows"] = await sync_workflows(db, client)
    except SupervityError as exc:
        result["errors"].append(f"workflows: {exc}")
        result["workflows"] = None

    try:
        result["runs"] = await sync_runs(db, client)
    except SupervityError as exc:
        result["errors"].append(f"runs: {exc}")
        result["runs"] = None

    # A run synced while it was still executing keeps whatever partial timeline
    # Auto had published at that moment, and never asks again — the Orchestrator
    # cycle we watched live froze at 4 steps when it eventually recorded 10.
    # Re-fetch any run whose timeline was captured before the run finished.
    stale = (
        db.query(AgentRun)
        .filter(AgentRun.timeline_synced_at.isnot(None))
        .filter(AgentRun.auto_updated_at.isnot(None))
        .filter(AgentRun.timeline_synced_at < AgentRun.auto_updated_at)
        .all()
    )
    for row in stale:
        row.timeline_synced_at = None
    if stale:
        db.commit()

    pending = (
        db.query(AgentRun)
        .filter(AgentRun.timeline_synced_at.is_(None))
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .limit(timeline_limit)
        .all()
    )
    total_pending = db.query(AgentRun).filter(AgentRun.timeline_synced_at.is_(None)).count()

    synced = 0
    unavailable = 0
    for run in pending:
        try:
            outcome = await sync_run_timeline(db, client, run.auto_run_id)
            if outcome.get("unavailable"):
                unavailable += 1
            else:
                synced += 1
        except SupervityError as exc:
            result["errors"].append(f"timeline {run.auto_run_id}: {exc}")

    result["timelines"] = {
        "synced": synced,
        # Runs Auto lists but will not serve a timeline for. Reported, not hidden.
        "unavailable_on_auto": unavailable,
        "still_pending": max(total_pending - synced - unavailable, 0),
        "limit": timeline_limit,
    }

    # Policy evaluations live inside the step outputs we just mirrored, so
    # extract them now rather than making the UI ask separately. Imported here
    # to keep the module import graph acyclic.
    from .policy import ingest_evaluations

    try:
        result["policy_evaluations"] = ingest_evaluations(db)
    except Exception as exc:  # noqa: BLE001 - a sync must not fail over this
        log.warning("Policy evaluation ingestion failed: %s", exc)
        result["errors"].append(f"policy evaluations: {exc}")
        result["policy_evaluations"] = None

    # Agent escalations live in the same step outputs, so route them into the
    # Workbench queue in the same pass.
    from .workbench import ingest_exceptions

    try:
        result["workbench"] = ingest_exceptions(db)
    except Exception as exc:  # noqa: BLE001
        log.warning("Workbench exception ingestion failed: %s", exc)
        result["errors"].append(f"workbench: {exc}")
        result["workbench"] = None

    return result
