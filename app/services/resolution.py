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

# Operators are found by the shape of their input schema, never by name, so
# renaming one on Auto does not silently stop this working.
#
# The evidence Operator is the one that takes a ticket key and a confidence
# threshold — that pairing is what makes it the governed-decision step. The
# resolution Operator is the one that takes a ticket key plus the evidence and
# somewhere to send the notification; it is the only one that acts.
REQUIRED_INPUTS = ("issue_key", "min_auto_confidence")
RESOLVER_INPUTS = ("issue_key", "authoritative_evidence_json", "notification_recipient")

# The step whose output is the evidence package the resolution Operator expects.
EVIDENCE_STEP = "authoritative_evidence_reconciliation"

# The shape of a ticket reference, used only to tell a ticket apart from a
# cluster name in the Workbench. A format, not a value — no ticket key, project
# prefix or expected count is written down anywhere in this repository.
TICKET_KEY = re.compile(r"[A-Za-z][A-Za-z0-9]*-\d+")

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


async def find_operator(
    db: Session, client: SupervityClient, required: tuple[str, ...]
) -> tuple[AgentWorkflow, dict] | tuple[None, None]:
    """The Operator whose input schema contains every named input.

    The workflow list Auto returns is a summary and carries no input schema, so
    each definition is fetched to read it.

    Returns the workflow and the defaults it declares for its inputs. Nothing is
    invented: an input with no default stays absent, and the call fails loudly
    rather than running against a value this repo made up.
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
        if not all(name in names for name in required):
            continue

        defaults: dict[str, Any] = {}
        for spec in specs:
            name, value = spec.get("name"), spec.get("value")
            if name and value is not None and value != "":
                defaults[str(name)] = value
        return workflow, defaults

    return None, None


async def find_evidence_operator(db: Session, client: SupervityClient):
    return await find_operator(db, client, REQUIRED_INPUTS)


def _decided_keys(db: Session) -> set[str]:
    """Tickets the Operator has already given a verdict on."""
    return {d["issue_key"] for d in read_decisions(db)["decisions"]}


def pending_ticket_keys(
    db: Session, limit: int, *, skip_decided: bool = True
) -> tuple[list[str], str | None]:
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
    # Tickets already decided are skipped, so calling this repeatedly walks
    # forward through the backlog instead of re-asking about the same few. That
    # is what lets a sweep run to exhaustion in chunks rather than stopping at
    # whatever the first batch happened to contain.
    seen: set[str] = _decided_keys(db) if skip_decided else set()
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
    #
    # Every open item is scanned, not the first few. Capping the scan at a
    # multiple of the batch size made a sweep report "no tickets left" while
    # tickets remained further down the queue — a batch loop that stops early
    # and calls itself finished is exactly the failure this build argues
    # against. Most items are already decided or are cluster-level, so the scan
    # has to reach past them.
    if len(keys) < limit:
        from ..models.workbench import WorkbenchException

        for item in (
            db.query(WorkbenchException)
            .filter(WorkbenchException.status == "open")
            .order_by(WorkbenchException.created_at.desc())
            .all()
        ):
            # Workbench items also cover ticket classes and clusters, whose refs
            # are cluster names rather than tickets. The evidence Operator takes
            # a single ticket, so only refs shaped like a ticket key are asked
            # about. A shape, not a value — no key is written down here.
            key = item.subject_ref
            if key and not TICKET_KEY.fullmatch(str(key)):
                continue
            if key and str(key) not in seen:
                seen.add(str(key))
                keys.append(str(key))
                source = source or "the Workbench queue"
            if len(keys) >= limit:
                break

    # Routing decisions and the Workbench are the tickets that reached a
    # decision point. They are a fraction of the dataset — the Orchestrator
    # routes a handful per cycle — so on their own they cap the pipeline at a
    # few dozen tickets while hundreds sit unexamined in the Operators' own
    # output.
    #
    # Anything the agents mentioned is a ticket the agents saw. Read the keys
    # out of the mirrored output and work through them too, after the tickets
    # that were explicitly routed. No key is invented: every one appears
    # verbatim in something an Operator emitted.
    #
    # Scavenging text for anything ticket-shaped also picks up knowledge
    # articles and incident records, which share the shape. The prefixes worth
    # keeping are the ones the agents actually route tickets under — read from
    # the explicit sources above rather than written down here, so a dataset
    # using different prefixes works without a change.
    # Taken from every ticket the agents have routed or already decided, not
    # only the ones still pending — once the pending list empties, the pending
    # list is no longer evidence of anything.
    prefixes = {
        k.split("-", 1)[0].upper() for k in list(keys) + list(seen) if "-" in k
    }

    if len(keys) < limit and prefixes:
        for activity, run in rows:
            payloads = [_parse_output(activity.outputs)]
            if activity.artifact_data:
                payloads.extend(activity.artifact_data.values())
            for payload in payloads:
                if payload is None:
                    continue
                for match in TICKET_KEY.finditer(json.dumps(payload, default=str)):
                    key = match.group(0)
                    if key.split("-", 1)[0].upper() not in prefixes:
                        continue
                    if key not in seen:
                        seen.add(key)
                        keys.append(key)
                        source = source or "the Operators' mirrored output"
                    if len(keys) >= limit:
                        break
                if len(keys) >= limit:
                    break
            if len(keys) >= limit:
                break

    return keys[:limit], source


# Phrases an Operator uses when a rule refuses, mapped to the evaluation that
# should be present if that rule ran. Matching on the reason text is crude, but
# the alternative is asserting nothing is missing, which was the bug.
REASON_TO_GATE: dict[str, tuple[str, ...]] = {
    "safe for automation": ("AUTO_SAFE", "X_AUTO_SAFE", "AUTOMATION_SAFETY"),
    "auto-safe": ("AUTO_SAFE", "X_AUTO_SAFE", "AUTOMATION_SAFETY"),
    "change": ("CHANGE", "CAB", "CHANGE_CONTROL"),
    "access change": ("ACCESS_CHANGE_BLOCK", "ACCESS"),
    "identity": ("IDENTITY",),
    "confidence": ("KB_CONFIDENCE", "CONFIDENCE"),
    "vip": ("VIP",),
}


def _reason_covered(reason: Any, evaluations: list) -> bool:
    """Is the rule the Operator gave as its reason among the gates it logged?

    True when nothing in the reason maps to a known gate — an unrecognised
    reason is not evidence of a gap. False only when a rule is clearly named
    and no matching evaluation was recorded.
    """
    if not isinstance(reason, str) or not reason.strip():
        return True

    text = reason.lower()
    logged = " ".join(
        str(e.get("policy_key", "")) + " " + str(e.get("policy_name", ""))
        for e in evaluations
        if isinstance(e, dict)
    ).upper()

    for phrase, keys in REASON_TO_GATE.items():
        if phrase in text and not any(key in logged for key in keys):
            return False
    return True


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
        evaluations = payload.get("policy_evaluations") or []
        by_ticket[str(key)] = {
            # Whether the rule named in the reason is among the logged gates.
            # ITSM-2180 showed five passing gates and a block, because the
            # Operator applied the auto-safe rule without recording it as an
            # evaluation. Five greens and an unexplained refusal reads as a
            # contradiction, and "every evaluation is logged" is a claim this
            # build makes. Flagging the gap keeps the claim honest; inventing
            # the missing gate would not.
            "deciding_rule_logged": _reason_covered(
                payload.get("decision_reason"), evaluations
            ),
            "issue_key": str(key),
            "decision": str(verdict),
            "auto_resolved": str(verdict).upper() in ALLOW_VERDICTS,
            "confidence": confidence if isinstance(confidence, (int, float)) else None,
            "reason": payload.get("decision_reason"),
            "policy_evaluations": evaluations,
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


def _evidence_for(db: Session, issue_key: str) -> dict | None:
    """The evidence package the Operator produced for one ticket, newest first.

    Handed to the resolution Operator verbatim. It is the Operator's own output,
    not a summary of it — the resolution Operator re-reads the policy verdict
    and the identity evidence out of this and would rightly refuse a version
    this repo had paraphrased.
    """
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )
    for activity, _run in rows:
        if (activity.step_id or "") != EVIDENCE_STEP:
            continue
        payload = _parse_output(activity.outputs)
        if isinstance(payload, dict) and str(payload.get("issue_key")) == issue_key:
            return payload
    return None


def _repo_from_issue_url(url: Any) -> str | None:
    """`owner/repo` out of a GitHub issue URL, or None if it is not one."""
    if not isinstance(url, str):
        return None
    match = re.search(r"github\.com/([^/\s]+)/([^/\s]+)/issues/", url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _already_resolved(db: Session) -> set[str]:
    """Tickets a resolution run has already acted on.

    Without this, a second sweep would email the same person twice about the
    same ticket. An action that reaches a real inbox has to be idempotent.
    """
    done: set[str] = set()
    rows = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .all()
    )
    for activity, _run in rows:
        payload = _parse_output(activity.outputs)
        if not isinstance(payload, dict):
            continue
        key = payload.get("issue_key")
        if not key:
            continue

        # A rejected run reports the same fields as a successful one, with null
        # values — it names what it *would* have sent. Treating the presence of
        # the key as proof of delivery marked a ticket resolved that the
        # Operator had refused, and then skipped it forever.
        #
        # Acted on means something actually went out: a comment posted, an email
        # sent, or the run itself reporting success.
        if str(payload.get("run_status") or "").upper() in ("REJECTED_INPUT", "FAILED"):
            continue

        delivered = any(
            str(payload.get(field) or "").upper() in ("SUCCESS", "SENT", "POSTED", "OK")
            for field in (
                "notification_status",
                "email_status",
                "resolution_status",
                "github_comment_status",
            )
        )
        if delivered:
            done.add(str(key))
    return done


def _resolution_outcome(result: Any) -> dict:
    """What the resolution run actually did, read from the run itself.

    The Operator answers synchronously, so its step outputs come back on the
    execute response. It reports delivery per channel and lists the guardrails
    that stopped it, and those are the only things worth believing here.
    """
    if not isinstance(result, dict):
        return {"status": "unconfirmed", "reason": "Auto returned no run detail."}

    email = github = None
    errors: list = []
    run_status = None

    for activity in result.get("activityRuns") or []:
        raw = (activity.get("outputs") or {}).get("output") or ""
        if "{" not in raw:
            continue
        try:
            payload = json.loads(raw[raw.find("{") :])
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        email = payload.get("email_status") or email
        github = payload.get("github_comment_url") or github
        run_status = payload.get("run_status") or run_status
        if payload.get("validation_errors"):
            errors = payload["validation_errors"]

    delivered = str(email or "").upper() in ("SENT", "SUCCESS") or bool(github)
    if delivered:
        return {
            "status": "resolved",
            "email_status": email,
            "github_comment_url": github,
        }

    if errors or str(run_status or "").upper() in ("REJECTED_INPUT", "FAILED"):
        return {
            "status": "refused",
            "reason": "; ".join(str(e) for e in errors)[:300]
            or f"The Operator returned {run_status}.",
        }

    # Nothing said either way — usually a reply cut off mid-run. Never reported
    # as resolved, because a retry is safer than a false claim.
    return {"status": "unconfirmed", "reason": "The run reported no delivery."}


async def resolve_allowed(
    db: Session, client: SupervityClient, limit: int = 25
) -> dict:
    """Hand every ticket the Operator cleared to the Operator that resolves it.

    This is the second half of the loop. An ALLOW that sits in a table is not a
    resolved ticket — the agent has to actually close it, comment on the issue
    of record, and tell the person who raised it.

    Nothing is decided here. The verdict was made by the evidence Operator, and
    the resolution Operator re-checks it against the evidence before acting.
    """
    from . import agent_sync

    workflow, defaults = await find_operator(db, client, RESOLVER_INPUTS)
    if workflow is None:
        return {
            "ran": False,
            "reason": (
                "No Operator on Auto takes a ticket key, an evidence package and "
                "a notification recipient, so there is nothing to resolve with."
            ),
        }

    # Where the evidence Operator looked this ticket up. Used when the evidence
    # itself carries no issue URL — it is the repository the agent actually read
    # from, so it is the system of record, rather than whichever repository this
    # Operator was last pointed at by hand.
    _evidence_wf, evidence_defaults = await find_evidence_operator(db, client)
    fallback_repo = (evidence_defaults or {}).get("github_repository")

    allowed = [d for d in read_decisions(db)["decisions"] if d["auto_resolved"]]
    done = _already_resolved(db)
    outstanding = [d for d in allowed if d["issue_key"] not in done]
    # Reported separately. Counting "everything this batch did not reach" as
    # already resolved turned a small `limit` into a claim that seven tickets
    # had been acted on when two had.
    skipped_already_done = len(allowed) - len(outstanding)
    todo = outstanding[:limit]
    not_reached = max(len(outstanding) - len(todo), 0)

    if not todo:
        return {
            "ran": True,
            "operator": workflow.name,
            "cleared_for_resolution": len(allowed),
            "already_resolved": skipped_already_done,
            "resolved_now": 0,
            "results": [],
            "note": "Every cleared ticket has already been acted on.",
        }

    results: list[dict] = []
    run_ids: list[str] = []

    for decision in todo:
        issue_key = decision["issue_key"]
        evidence = _evidence_for(db, issue_key)
        if evidence is None:
            results.append(
                {
                    "issue_key": issue_key,
                    "status": "skipped",
                    "reason": "No evidence package mirrored for this ticket.",
                }
            )
            continue

        inputs = {
            **(defaults or {}),
            "issue_key": issue_key,
            "authoritative_evidence_json": json.dumps(evidence),
        }

        # The resolution Operator's saved default for the repository is whatever
        # it was last run against by hand, and pointed at a repository that does
        # not hold these tickets. Take it from the issue URL in the evidence
        # instead: that is where the agent itself found this ticket, so a
        # comment posted there lands on the right issue.
        repo = _repo_from_issue_url(evidence.get("github_issue_url")) or fallback_repo
        if repo:
            inputs["github_repository"] = repo
        elif "github_repository" in inputs:
            results.append(
                {
                    "issue_key": issue_key,
                    "status": "skipped",
                    "reason": (
                        "The evidence carries no GitHub issue URL, so the target "
                        "repository cannot be established. Refusing to comment on "
                        "whichever repository was configured last."
                    ),
                }
            )
            continue
        try:
            result = await client.execute(workflow.auto_id, inputs=inputs)
        except SupervityError as exc:
            message = str(exc)
            # A lost reply is not a lost run: the Operator carries on and may
            # well have sent the email. Recorded as unconfirmed rather than
            # failed, so a retry does not send a second one.
            unconfirmed = "524" in message or "timed out" in message.lower()
            results.append(
                {
                    "issue_key": issue_key,
                    "status": "unconfirmed" if unconfirmed else "failed",
                    "reason": message[:200],
                }
            )
            continue

        run_id = None
        if isinstance(result, dict):
            run_id = result.get("id") or (result.get("workflowRun") or {}).get("id")
        if run_id:
            run_ids.append(run_id)

        # A run id means the Operator was asked, not that it agreed. It runs its
        # own guardrails on the evidence and refuses when they fail, and reading
        # a returned id as success reported three tickets resolved that the
        # Operator had rejected. Claiming an action the audit log denies is the
        # exact failure this whole build argues against, so the outcome is read
        # out of the run itself.
        detail = result
        if run_id:
            try:
                detail = await client.get_run(run_id)
            except SupervityError as exc:
                log.warning("Could not read resolution run %s: %s", run_id, exc)
        outcome = _resolution_outcome(detail)
        results.append(
            {
                "issue_key": issue_key,
                "status": outcome["status"],
                "confidence": decision["confidence"],
                "auto_run_id": run_id,
                **({"reason": outcome["reason"]} if outcome.get("reason") else {}),
                **(
                    {"email_status": outcome["email_status"]}
                    if outcome.get("email_status")
                    else {}
                ),
                **(
                    {"github_comment_url": outcome["github_comment_url"]}
                    if outcome.get("github_comment_url")
                    else {}
                ),
            }
        )

    for run_id in run_ids:
        try:
            await agent_sync.sync_run_timeline(db, client, run_id)
        except SupervityError as exc:
            log.warning("Could not mirror resolution run %s: %s", run_id, exc)

    return {
        "ran": True,
        "operator": workflow.name,
        "cleared_for_resolution": len(allowed),
        "already_resolved": skipped_already_done,
        # Cleared, not yet acted on, and outside this batch. Not a claim of
        # anything having happened to them.
        "not_reached_this_batch": not_reached,
        "resolved_now": sum(1 for r in results if r["status"] == "resolved"),
        # Asked and refused by the Operator's own guardrails. Counted, never
        # folded into the resolved figure.
        "refused": sum(1 for r in results if r["status"] == "refused"),
        "unconfirmed": sum(1 for r in results if r["status"] == "unconfirmed"),
        "results": results,
    }


async def decide_one(
    db: Session, client: SupervityClient, issue_key: str
) -> dict:
    """Ask the evidence Operator about one ticket, under the live thresholds.

    Returns the verdict before and after, so a threshold edit can be shown to
    have changed the agent's mind on a named ticket rather than on whichever
    tickets a sweep happened to reach.
    """
    from . import agent_sync
    from .policy import effective_inputs

    workflow, defaults = await find_evidence_operator(db, client)
    if workflow is None:
        return {
            "ran": False,
            "reason": "No Operator on Auto takes a single issue_key with a "
            "confidence threshold.",
        }

    before = next(
        (d for d in read_decisions(db)["decisions"] if d["issue_key"] == issue_key),
        None,
    )

    inputs = {**(defaults or {})}
    try:
        inputs.update({k: v for k, v in effective_inputs(db).items() if k in inputs})
    except Exception as exc:  # noqa: BLE001 - fall back to the Operator's defaults
        log.warning("Could not read policy inputs: %s", exc)
    inputs["issue_keys"] = ""
    inputs["issue_key"] = issue_key

    run_id = None
    try:
        result = await client.execute(workflow.auto_id, inputs=inputs)
        if isinstance(result, dict):
            run_id = result.get("id") or (result.get("workflowRun") or {}).get("id")
    except SupervityError as exc:
        message = str(exc)
        # The edge closes the connection at 100 seconds while the Operator is
        # still working. The run completes regardless, so find it rather than
        # reporting a failure that did not happen.
        if not ("524" in message or "timed out" in message.lower()):
            return {"ran": False, "reason": message[:300]}
        try:
            recent, _pagination = await client.list_runs(limit=25)
            for run in recent:
                if run.get("workflowId") == workflow.auto_id:
                    run_id = run.get("id")
                    break
        except SupervityError:
            pass

    if run_id:
        try:
            await agent_sync.sync_run_timeline(db, client, run_id)
        except SupervityError as exc:
            log.warning("Could not mirror run %s: %s", run_id, exc)

    after = next(
        (d for d in read_decisions(db)["decisions"] if d["issue_key"] == issue_key),
        None,
    )

    return {
        "ran": True,
        "issue_key": issue_key,
        "thresholds_in_force": {
            k: inputs.get(k)
            for k in ("min_auto_confidence", "vip_requires_approval")
        },
        "before": {
            "decision": (before or {}).get("decision"),
            "confidence": (before or {}).get("confidence"),
        },
        "after": {
            "decision": (after or {}).get("decision"),
            "confidence": (after or {}).get("confidence"),
            "reason": (after or {}).get("reason"),
        },
        "changed": bool(before and after and before["decision"] != after["decision"]),
        "auto_run_id": run_id,
    }


async def sweep(
    db: Session,
    client: SupervityClient,
    limit: int = 20,
    concurrency: int = 3,
    resolve: bool = True,
    redecide: bool = False,
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

    keys, queue_source = pending_ticket_keys(db, limit, skip_decided=not redecide)
    if not keys:
        return {
            "ran": False,
            "reason": (
                "No routed tickets have been mirrored yet, so there are no "
                "ticket keys to ask about. Run the Orchestrator, then sync."
                if redecide
                else "Every routed ticket already has a verdict. Use re-decide "
                "to ask again under the thresholds now in force."
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
        # Closing the loop: a ticket the agent cleared is not resolved until the
        # agent has actually resolved it, commented on the issue of record and
        # told the person who raised it.
        "resolution": (await resolve_allowed(db, client)) if resolve else None,
        "result": read_decisions(db),
        "remaining_undecided": len(pending_ticket_keys(db, 10_000)[0]),
    }
