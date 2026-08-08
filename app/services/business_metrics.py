"""
The four business metrics this project is judged on: MTTR, SLA compliance,
auto-resolution rate and CSAT — plus deflection, which is our own.

Every figure is lifted from what an Operator on Supervity Auto actually
reported. Nothing is computed from raw tickets here, because that would mean
this repo and the agents could disagree about the same number. Where an Operator
has not reported a metric, it is returned as null with a note naming the
Operator that would produce it. A dash on screen is honest; a zero is not.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun, AgentWorkflow

log = logging.getLogger(__name__)


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


def _payloads(activity: AgentActivity) -> list:
    """Both places an Operator's result can arrive: inline, or a downloaded file."""
    found = []
    inline = _parse_output(activity.outputs)
    if inline is not None:
        found.append(inline)
    if activity.artifact_data:
        found.extend(activity.artifact_data.values())
    return found


def _walk(node: Any, depth: int = 0) -> Iterable[dict]:
    """Every dict inside a payload, depth-limited."""
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
        cleaned = value.strip().rstrip("%")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _newest_run_per_workflow(db: Session) -> dict[str, int]:
    """Only the most recent run of each workflow counts.

    Re-running an Operator supersedes the earlier result. Reading every run
    would mix figures computed under different prompts and thresholds.
    """
    rows = (
        db.query(AgentRun)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )
    names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}
    newest: dict[str, int] = {}
    for run in rows:
        key = run.workflow_name or names.get(run.auto_workflow_id) or run.auto_workflow_id
        if key and key not in newest:
            newest[key] = run.id
    return newest


def _activities_for(db: Session, run_ids: Iterable[int]) -> list[AgentActivity]:
    ids = list(run_ids)
    if not ids:
        return []
    return db.query(AgentActivity).filter(AgentActivity.run_id.in_(ids)).all()


def collect(db: Session) -> dict:
    """Assemble the judged metrics from the newest run of each Operator."""
    newest = _newest_run_per_workflow(db)
    activities = _activities_for(db, newest.values())

    run_by_id = {r.id: r for r in db.query(AgentRun).all()}
    workflow_names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}

    csat: dict | None = None
    sla: dict | None = None
    resolution: dict | None = None
    deflection: dict | None = None
    knowledge: dict | None = None
    sources: dict[str, str] = {}

    for activity in activities:
        run = run_by_id.get(activity.run_id)
        origin = (
            (run.workflow_name if run else None)
            or (workflow_names.get(run.auto_workflow_id) if run else None)
            or "unknown workflow"
        )

        for payload in _payloads(activity):
            for node in _walk(payload):
                # --- CSAT ------------------------------------------------
                if csat is None and "overall_average" in node:
                    average = _num(node.get("overall_average"))
                    if average is not None:
                        csat = {
                            "average": round(average, 2),
                            "responses": _num(node.get("total_responses")),
                            "response_rate_pct": _num(node.get("response_rate")),
                        }
                        sources["csat"] = origin

                # --- SLA, from the triage operator's basis counts ---------
                if sla is None and "business_hours" in node and "elapsed_fallback" in node:
                    on_calendar = _num(node.get("business_hours")) or 0
                    fallback = _num(node.get("elapsed_fallback")) or 0
                    total = on_calendar + fallback
                    if total:
                        sla = {
                            "tickets_measured": int(total),
                            "on_business_hours": int(on_calendar),
                            "elapsed_fallback": int(fallback),
                            # How much of the SLA picture is authoritative
                            # rather than a rough estimate.
                            "authoritative_pct": round(100.0 * on_calendar / total, 1),
                        }
                        sources["sla"] = origin

                # --- Deflection, split as the Correlator reports it -------
                if deflection is None and (
                    "incident_collapse" in node or "elimination_forecast" in node
                ):
                    collapse = node.get("incident_collapse")
                    forecast = node.get("elimination_forecast")

                    def _block(v):
                        if isinstance(v, dict):
                            count = _num(v.get("count"))
                            return (
                                {
                                    "count": int(count),
                                    "share_pct": _num(v.get("population_share_pct")),
                                }
                                if count is not None
                                else None
                            )
                        count = _num(v)
                        return {"count": int(count), "share_pct": None} if count is not None else None

                    collapse_block = _block(collapse)
                    forecast_block = _block(forecast)
                    if collapse_block or forecast_block:
                        deflection = {
                            "collapsed_now": collapse_block,
                            "preventable": forecast_block,
                        }
                        sources["deflection"] = origin

                # --- Knowledge articles drafted --------------------------
                if knowledge is None and isinstance(node.get("drafted_articles"), list):
                    drafts = node["drafted_articles"]
                    if drafts:
                        knowledge = {
                            "articles_drafted": len(drafts),
                            "awaiting_approval": len(drafts),
                        }
                        sources["knowledge"] = origin

    # --- Auto-resolution -------------------------------------------------
    #
    # Two sources, and the Orchestrator's is better. A single-ticket Operator
    # run contributes one decision; the Orchestrator's router decides a whole
    # cycle at once. Preferring the router keeps the rate representative of a
    # batch rather than of whichever tickets happened to be tested by hand.
    router_counts: dict[str, int] | None = None
    router_origin: str | None = None
    for activity in activities:
        run = run_by_id.get(activity.run_id)
        origin = (
            (run.workflow_name if run else None)
            or (workflow_names.get(run.auto_workflow_id) if run else None)
            or "unknown workflow"
        )
        for payload in _payloads(activity):
            for node in _walk(payload):
                counts = node.get("counts")
                if (
                    router_counts is None
                    and isinstance(counts, dict)
                    and "allowed" in counts
                    and ("review" in counts or "blocked" in counts)
                ):
                    total = sum(
                        int(_num(v) or 0)
                        for k, v in counts.items()
                        if k in ("allowed", "blocked", "review")
                    )
                    if total:
                        router_counts = {
                            k: int(_num(v) or 0)
                            for k, v in counts.items()
                            if k in ("allowed", "blocked", "review")
                        }
                        router_origin = origin

    # Per-ticket verdicts, counted once per ticket rather than once per mention.
    # Read through the same code the resolution page uses, so the Dashboard and
    # that page can never report different rates off the same runs. Scanning
    # activity payloads directly counted a ticket again for every step that
    # echoed its decision, and only saw the newest run of each workflow — which
    # left the Dashboard reporting four decisions where nineteen tickets had
    # been decided.
    from .resolution import _already_resolved, read_decisions

    per_ticket = read_decisions(db)
    acted_on = _already_resolved(db)
    decisions: dict[str, int] = {}
    for entry in per_ticket["decisions"]:
        key = str(entry["decision"]).strip().upper().replace(" ", "_")
        decisions[key] = decisions.get(key, 0) + 1

    if router_counts:
        allowed = router_counts.get("allowed", 0)
        total_decisions = sum(router_counts.values())
        resolution = {
            "decisions": total_decisions,
            "allowed": allowed,
            "human_review": router_counts.get("review", 0),
            "blocked": router_counts.get("blocked", 0),
            "auto_resolution_rate_pct": round(100.0 * allowed / total_decisions, 1),
            "breakdown": router_counts,
            "basis": "orchestrator_cycle",
        }
        sources["resolution"] = router_origin or "unknown workflow"
    elif decisions:
        total_decisions = sum(decisions.values())
        allowed = decisions.get("ALLOW", 0)
        resolution = {
            "decisions": total_decisions,
            "allowed": allowed,
            "human_review": decisions.get("HUMAN_REVIEW", 0),
            "blocked": decisions.get("BLOCK", 0)
            + decisions.get("BLOCKED", 0)
            + decisions.get("DENY", 0),
            "auto_resolution_rate_pct": round(100.0 * allowed / total_decisions, 1),
            "breakdown": decisions,
            # Individual Operator runs, not a full cycle. Say so, because a rate
            # from three hand-picked tickets is not the same claim as one from
            # a batch the Orchestrator chose.
            "basis": "individual_operator_runs",
            "avg_confidence": per_ticket["avg_confidence"],
            "decisions_without_confidence": per_ticket["decisions_without_confidence"],
            # Cleared is not the same as done. A ticket the agent judged safe
            # still has to be resolved, commented on and communicated, and the
            # resolution Operator runs its own guardrails on the evidence and
            # sometimes refuses. Reporting only the rate invites the reader to
            # assume every cleared ticket was acted on.
            "acted_on": len(acted_on),
            "cleared_awaiting_action": max(allowed - len(acted_on), 0),
        }
        sources["resolution"] = "Ticket Evidence and Policy Operator"

    # MTTR needs resolution timestamps that no Operator reports yet. Saying so
    # is better than deriving a number the agents would not recognise.
    missing: list[str] = []
    if csat is None:
        missing.append("CSAT — run the CSAT and Knowledge Loop Operator")
    if sla is None:
        missing.append("SLA basis — run the Ticket Queue Triage Operator")
    if resolution is None:
        missing.append("Auto-resolution — no Operator has recorded a decision yet")
    if deflection is None:
        missing.append("Deflection — run the Major-Incident Correlator Operator")

    return {
        "csat": csat,
        "sla": sla,
        "resolution": resolution,
        "deflection": deflection,
        "knowledge": knowledge,
        # MTTR is deliberately absent rather than estimated. See above.
        "mttr": None,
        "mttr_note": (
            "No Operator reports resolution timestamps yet, so MTTR would have to "
            "be inferred here, and this repo does not compute metrics the agents "
            "have not produced."
        ),
        "sources": sources,
        "missing": missing,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
