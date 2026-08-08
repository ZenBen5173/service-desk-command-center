"""
Auto-resolution: ask the evidence Operator about one ticket at a time.

The Orchestrator calls its Operators as sub-workflows and gets nothing back —
Auto returns zero bytes to the parent, so no per-ticket confidence ever reaches
the routing step. With no confidence to compare against the policy threshold,
the Orchestrator does the only safe thing and escalates everything. Auto-
resolution in a batch cycle is therefore structurally zero, and no amount of
prompt or mapping work on Auto has moved it.

The same Operator answers perfectly when asked about a single ticket. So this
module asks it one ticket at a time, over the same public execute endpoint the
Orchestrator uses.

What this is not: a second decision engine. Every ALLOW, every BLOCK, every
confidence score and every policy evaluation below is produced by the Operator
on Supervity Auto. Nothing here evaluates a policy, scores a match or overrides
a verdict. It chooses which ticket to ask about, and it records the answer.

Which Operator to ask is discovered from the input schemas mirrored from Auto,
not from a workflow name — renaming an Operator there must not silently stop
this working. Which tickets to ask about come from the triage queue an Operator
already produced, so no ticket key is ever authored here.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun, AgentWorkflow
from .supervity import SupervityClient, SupervityError

log = logging.getLogger(__name__)

# The single-ticket evidence Operator is the one whose input schema takes a
# ticket key and a confidence threshold. That pairing is what makes it the
# governed-decision step, and it survives the workflow being renamed.
REQUIRED_INPUTS = ("issue_key", "min_auto_confidence")

# Steps whose output carries the Operator's final verdict. Earlier steps in the
# same run also emit an issue_key, so reading any of them would mistake a
# validation echo for a decision.
VERDICT_STEPS = ("governed_decision", "authoritative_evidence_reconciliation")

# Verdicts that mean the agent judged the ticket safe to resolve without a
# person. Anything else counts as escalated, including values we have not seen
# before — an unrecognised verdict must never be read as approval.
ALLOW_VERDICTS = ("ALLOW", "AUTO_RESOLVE", "APPROVED", "SAFE_TO_RESOLVE")


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
        match = re.search(r"\{.*\}", inner, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except (ValueError, TypeError):
            return None
    return inner


async def find_evidence_operator(
    db: Session, client: SupervityClient
) -> tuple[AgentWorkflow, dict] | tuple[None, None]:
    """The Operator that decides a single ticket, found by its input schema.

    The workflow list Auto returns is a summary and carries no input schema, so
    each definition is fetched to read it. Matching on the schema rather than on
    a name means renaming the Operator on Auto does not silently break this.

    Returns the workflow and the defaults declared for its inputs.
    """
    for workflow in db.query(AgentWorkflow).all():
        try:
            payload = await client.get_workflow(workflow.auto_id)
        except SupervityError as exc:
            log.warning("Could not read %s from Auto: %s", workflow.name, exc)
            continue

        inner = (payload.get("workflow") or payload) if isinstance(payload, dict) else {}
        specs = [i for i in (inner.get("inputs") or []) if isinstance(i, dict)]
        names = {str(i.get("name")) for i in specs}
        if not all(required in names for required in REQUIRED_INPUTS):
            continue

        # The Operator's own declared default for each input. Nothing is invented
        # here: an input with no default stays absent, and the call fails loudly
        # rather than running against a value this repo made up.
        defaults: dict[str, Any] = {}
        for spec in specs:
            name, value = spec.get("name"), spec.get("value")
            if name and value is not None and value != "":
                defaults[str(name)] = value
        return workflow, defaults

    return None, None


def pending_ticket_keys(db: Session, limit: int) -> tuple[list[str], str | None]:
    """Ticket keys to ask about, and where they came from.

    The Orchestrator records every ticket it routed and the rule that decided
    it. Those routing decisions are the population this exists to re-ask about,
    so they come first — and within them, the ones the confidence gate stopped
    come before the rest, because a ticket escalated for "confidence 0.00" is
    precisely the one whose confidence never arrived.

    Tickets blocked by change control or an access rule are still asked about.
    The Operator applies those same policies itself and will block them again;
    filtering them out here would be this repo pre-judging a policy question
    that belongs to the agent.
    """
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )

    gated: list[str] = []
    other: list[str] = []
    seen: set[str] = set()
    source: str | None = None

    for activity, run in rows:
        payload = _parse_output(activity.outputs)
        if not isinstance(payload, dict):
            continue
        decisions = payload.get("routing_decisions")
        if not isinstance(decisions, list):
            continue
        for entry in decisions:
            if not isinstance(entry, dict):
                continue
            key = entry.get("issue_key")
            if not key or str(key) in seen:
                continue
            seen.add(str(key))
            source = source or (run.workflow_name or "the Orchestrator")
            if str(entry.get("deciding_rule") or "") == "confidence_gate":
                gated.append(str(key))
            else:
                other.append(str(key))

    keys = gated + other

    # The Orchestrator only routes a few tickets per cycle, so its history alone
    # is a thin sample. The Workbench holds every ticket that reached a person,
    # which is the same population seen from the other end.
    if len(keys) < limit:
        from ..models.workbench import WorkbenchException

        for item in (
            db.query(WorkbenchException)
            .filter(WorkbenchException.status == "open")
            .order_by(WorkbenchException.created_at.desc())
            .limit(limit * 3)
            .all()
        ):
            key = getattr(item, "issue_key", None)
            if key and str(key) not in seen:
                seen.add(str(key))
                keys.append(str(key))
                source = source or "the Workbench queue"
            if len(keys) >= limit:
                break

    return keys[:limit], source


def read_decisions(db: Session) -> dict:
    """Every per-ticket verdict the Operator has produced, as it reported them.

    One ticket asked twice keeps the newest answer. A threshold edit changes
    what the Operator decides, so an older verdict is a superseded opinion, not
    a second data point.
    """
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )

    by_ticket: dict[str, dict] = {}
    for activity, run in rows:
        if (activity.step_id or "") not in VERDICT_STEPS:
            continue
        payload = _parse_output(activity.outputs)
        if not isinstance(payload, dict):
            continue
        key = payload.get("issue_key")
        verdict = payload.get("decision")
        if not key or not verdict:
            continue
        if key in by_ticket:  # newest run wins; rows are newest-first
            continue

        confidence = payload.get("confidence")
        by_ticket[str(key)] = {
            "issue_key": str(key),
            "decision": str(verdict),
            "auto_resolved": str(verdict).upper() in ALLOW_VERDICTS,
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "reason": payload.get("decision_reason"),
            "policy_evaluations": payload.get("policy_evaluations") or [],
            "auto_run_id": run.auto_run_id,
            "workflow_name": run.workflow_name,
            "decided_at": run.auto_created_at.isoformat() if run.auto_created_at else None,
        }

    decisions = sorted(
        by_ticket.values(), key=lambda d: d["decided_at"] or "", reverse=True
    )
    allowed = [d for d in decisions if d["auto_resolved"]]
    scored = [d["confidence"] for d in decisions if d["confidence"] is not None]

    return {
        "decisions": decisions,
        "tickets_decided": len(decisions),
        "auto_resolved": len(allowed),
        "escalated": len(decisions) - len(allowed),
        "auto_resolution_rate_pct": (
            round(100.0 * len(allowed) / len(decisions), 1) if decisions else None
        ),
        "avg_confidence": round(sum(scored) / len(scored), 3) if scored else None,
        # Confidence is missing on some verdicts. Reported rather than treated as
        # zero — a blank means the Operator did not say, not that it was unsure.
        "decisions_without_confidence": len(decisions) - len(scored),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def sweep(
    db: Session,
    client: SupervityClient,
    limit: int = 20,
    concurrency: int = 3,
) -> dict:
    """Ask the evidence Operator about each pending ticket, one call per ticket.

    Runs a few at a time: Auto rate-limits, and a demo machine waiting on a
    sequential sweep of twenty tickets is a worse failure than a slow one.
    """
    from . import agent_sync

    workflow, defaults = await find_evidence_operator(db, client)
    if workflow is None:
        return {
            "ran": False,
            "reason": (
                "No Operator on Auto takes a single issue_key with a confidence "
                "threshold. Sync workflows first, or check the Operator's inputs."
            ),
        }

    keys, queue_source = pending_ticket_keys(db, limit)
    if not keys:
        return {
            "ran": False,
            "reason": (
                "No routed tickets have been mirrored yet, so there are no ticket "
                "keys to ask about. Run the Orchestrator, then sync."
            ),
        }

    # The live policies decide the thresholds, not the Operator's saved
    # defaults. Editing the confidence gate in the Command Center has to change
    # what the agent is asked on the next run, or the policies are decoration.
    from .policy import effective_inputs

    base = {**(defaults or {})}
    try:
        base.update({k: v for k, v in effective_inputs(db).items() if k in base})
    except Exception as exc:  # noqa: BLE001 - fall back to the Operator's own defaults
        log.warning("Could not read policy inputs, using Operator defaults: %s", exc)

    # This asks about one ticket. The Operator also accepts a list, and leaving
    # a stale one in place would send it down the batch path — the exact path
    # that returns nothing.
    base["issue_keys"] = ""

    thresholds = {k: base.get(k) for k in ("min_auto_confidence", "vip_requires_approval")}

    semaphore = asyncio.Semaphore(max(1, concurrency))
    run_ids: list[str] = []
    failures: list[dict] = []

    # Auto sits behind Cloudflare, which closes the connection at 100 seconds.
    # The Operator regularly takes longer than that, so `execute` returns a 524
    # while the run carries on server-side and completes normally. Losing the
    # reply is not the same as losing the run: these are recorded as detached
    # and collected from the run list afterwards, because throwing away a
    # completed decision would understate what the agent actually did.
    started_at = datetime.now(timezone.utc)
    detached: list[str] = []

    async def ask(issue_key: str) -> None:
        async with semaphore:
            try:
                result = await client.execute(
                    workflow.auto_id, inputs={**base, "issue_key": issue_key}
                )
            except SupervityError as exc:
                message = str(exc)
                if "524" in message or "timed out" in message.lower():
                    detached.append(issue_key)
                else:
                    failures.append({"issue_key": issue_key, "error": message[:200]})
                return
            run_id = None
            if isinstance(result, dict):
                run_id = result.get("id") or (result.get("workflowRun") or {}).get("id")
            if run_id:
                run_ids.append(run_id)
            else:
                failures.append(
                    {"issue_key": issue_key, "error": "Auto returned no run id"}
                )

    await asyncio.gather(*(ask(k) for k in keys))

    # Collect the runs whose reply was lost. Matched on this Operator and on
    # having started after the sweep did, so an older run is never claimed as
    # one of ours.
    if detached:
        try:
            recent, _pagination = await client.list_runs(limit=100)
            for run in recent:
                if run.get("workflowId") != workflow.auto_id:
                    continue
                created = run.get("createdAt")
                if not created:
                    continue
                try:
                    when = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if when >= started_at and run.get("id") not in run_ids:
                    run_ids.append(run["id"])
        except SupervityError as exc:
            failures.append({"error": f"Could not list runs to recover: {exc}"[:200]})

    # Mirror what came back, so the decisions are readable from the local store
    # like every other piece of agent output.
    mirrored = 0
    for run_id in run_ids:
        try:
            await agent_sync.sync_run_timeline(db, client, run_id)
            mirrored += 1
        except SupervityError as exc:
            failures.append({"run_id": run_id, "error": str(exc)[:200]})

    from .policy import ingest_evaluations

    try:
        ingest_evaluations(db)
    except Exception as exc:  # noqa: BLE001 - a sweep must not fail over this
        log.warning("Policy ingestion after sweep failed: %s", exc)

    return {
        "ran": True,
        "operator": workflow.name,
        "queue_source": queue_source,
        # The thresholds actually sent, so a rate can be read against the policy
        # that produced it rather than against whatever is in force later.
        "thresholds_in_force": thresholds,
        "tickets_asked": len(keys),
        "runs_started": len(run_ids),
        "runs_mirrored": mirrored,
        # Runs whose reply was cut off by the 100-second edge timeout and were
        # recovered from the run list. Reported rather than hidden — a number
        # that quietly excludes something is the failure this build argues
        # against.
        "replies_lost_to_timeout": len(detached),
        "failures": failures,
        "result": read_decisions(db),
    }
