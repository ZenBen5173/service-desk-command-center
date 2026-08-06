"""
Elimination Backlog — ranked classes of ticket worth making stop existing.

The distinction that matters for this project: the *judgement* about which
tickets share a root cause, what the permanent fix is, and whether a class is a
systemic failure or a knowledge gap, is made by Operators running on Supervity
Auto. This module does not cluster, classify or decide anything. It reads what
the Operators already emitted, normalises the field names, ranks by cost, and
hands it to the UI.

That boundary is not a style preference. Rebuilding Operator logic in this repo
is disqualifying for the hackathon, and duplicating it would also mean the
Command Center could disagree with the agent about what happened.

Agents write their structured payload as a JSON *string* under
`outputs["output"]`, so extraction parses rather than assumes a dict.
"""

import json
import logging
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models.agent import AgentActivity, AgentRun

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field mapping.
#
# Auto generates step code from a natural-language prompt, so the same concept
# can arrive under slightly different key names between rebuilds of a workflow.
# Listing accepted aliases is field mapping, not hardcoding data: no ticket key,
# person, count or decision appears here, and an unrecognised payload is
# reported rather than guessed at.
# ---------------------------------------------------------------------------

CLASS_COLLECTION_KEYS = ("clusters", "classes", "ticket_classes", "backlog", "groups")

# Operators may report deflection once for the whole run rather than per class.
# That figure is the agent's own, and is reported alongside — never merged into
# the per-class forecasts, so the two can be told apart.
RUN_DEFLECTION_KEYS = ("deflection", "deflection_summary", "deflection_totals")
RUN_DEFLECTION_VALUE_KEYS = (
    "tickets_deflected",
    "total_deflected",
    "deflected",
    "deflection_total",
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "key": ("cluster_key", "class_key", "key", "id", "cluster_id", "class_id"),
    "label": ("label", "name", "title", "symptom", "class", "summary", "description"),
    "classification": (
        "classification",
        "treatment",
        "category",
        "type",
        "class_type",
        "verdict",
    ),
    "volume": (
        "volume",
        "member_count",
        "ticket_count",
        "count",
        "tickets",
        "size",
        "num_tickets",
    ),
    "distinct_reporters": (
        "distinct_reporters",
        "distinct_reporter_count",
        "reporter_count",
        "unique_reporters",
        "users_affected",
    ),
    "breaches": (
        "breaches",
        "breach_count",
        "breached",
        "sla_breaches",
        "breached_count",
    ),
    "poor_csat_count": (
        "poor_csat_count",
        "poor_score_count",
        "low_csat_count",
        "poor_scores",
        "negative_csat",
    ),
    "avg_csat": ("avg_csat", "average_csat", "csat_average", "avg_score", "mean_csat"),
    "handling_hours": (
        "handling_hours",
        "handle_hours",
        "effort_hours",
        "total_handling_hours",
        "hours_spent",
    ),
    "has_kb_article": (
        "has_kb_article",
        "article_match",
        "kb_match",
        "has_article",
        "kb_article_exists",
    ),
    "proposed_fix": (
        "proposed_fix",
        "permanent_fix",
        "recommended_fix",
        "fix",
        "remediation",
        "recommendation",
    ),
    "owning_team": ("owning_team", "assignment_group", "team", "owner", "owning_group"),
    "deflection_forecast": (
        "deflection_forecast",
        "tickets_deflected",
        "deflection",
        "forecast",
        "preventable_tickets",
    ),
    "languages": ("languages", "langs", "detected_languages"),
    "members": ("members", "member_keys", "issue_keys", "tickets", "ticket_keys"),
}

# Classifications that mean "a human must approve before anything ships".
NEEDS_APPROVAL = {"MAJOR_INCIDENT", "REPEAT_FAILURE", "KNOWLEDGE_GAP", "ARTICLE_INEFFECTIVE"}


def _first(payload: dict, aliases: Iterable[str]) -> Any:
    """First present, non-null value among the accepted key names."""
    for alias in aliases:
        if alias in payload and payload[alias] is not None:
            return payload[alias]
    # Try a case-insensitive pass before giving up — generated code varies.
    lowered = {str(k).lower(): v for k, v in payload.items()}
    for alias in aliases:
        value = lowered.get(alias.lower())
        if value is not None:
            return value
    return None


def _as_number(value: Any) -> float | None:
    """Coerce to a number, or None. Never substitutes a zero for missing data."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", ""))
        except ValueError:
            return None
    if isinstance(value, (list, tuple)):
        return float(len(value))
    return None


def _as_int(value: Any) -> int | None:
    num = _as_number(value)
    return None if num is None else int(round(num))


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        # A fix is often an object; keep it readable without losing detail.
        for key in ("summary", "description", "text", "action", "title"):
            if isinstance(value.get(key), str):
                return value[key].strip() or None
        return json.dumps(value)[:500]
    if isinstance(value, (list, tuple)):
        parts = [p for p in (_as_text(v) for v in value) if p]
        return "; ".join(parts) if parts else None
    return str(value)


def _parse_output(outputs: Any) -> Any:
    """Unwrap an activity's payload.

    Auto puts the real result in `outputs["output"]` as a JSON string. Some
    steps return a bare boolean or plain text instead, which is fine — those
    simply contain nothing to extract.
    """
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


def _find_class_collections(node: Any, depth: int = 0) -> list[tuple[str, list]]:
    """Locate lists of ticket-class objects anywhere in a payload.

    Recursive because Operators nest their results differently depending on how
    Auto generated the step. Depth-limited so a pathological payload cannot
    stall a request.
    """
    found: list[tuple[str, list]] = []
    if depth > 6:
        return found

    if isinstance(node, dict):
        for key, value in node.items():
            if (
                str(key).lower() in CLASS_COLLECTION_KEYS
                and isinstance(value, list)
                and value
                and all(isinstance(item, dict) for item in value)
            ):
                found.append((str(key), value))
            else:
                found.extend(_find_class_collections(value, depth + 1))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_class_collections(item, depth + 1))
    return found


def _split_block(value: Any) -> dict | None:
    """Read a {count, population_share_pct} block as the Operator reported it."""
    if not isinstance(value, dict):
        count = _as_int(value)
        return {"count": count, "share_pct": None} if count is not None else None
    count = _as_int(_first(value, ("count", "total", "tickets", "value")))
    if count is None:
        return None
    return {
        "count": count,
        "share_pct": _as_number(
            _first(value, ("population_share_pct", "share_pct", "percent", "pct"))
        ),
    }


def _find_run_deflection(node: Any, depth: int = 0) -> dict | None:
    """Find the run-level deflection the Operator reported.

    Two shapes are accepted. The better one splits deflection into work avoided
    now by collapsing an incident, and volume a permanent fix would prevent
    later — those are different claims and blending them into one headline is
    not defensible. The older single-total shape is still read so an earlier
    run keeps rendering.

    Nothing here computes deflection. If the agent did not report it, none is
    shown.
    """
    if depth > 6:
        return None

    if isinstance(node, dict):
        collapse = _split_block(_first(node, ("incident_collapse", "collapse")))
        forecast = _split_block(
            _first(node, ("elimination_forecast", "prevention_forecast"))
        )
        if collapse or forecast:
            consolidation = node.get("consolidation")
            return {
                "incident_collapse": collapse,
                "elimination_forecast": forecast,
                "consolidation": consolidation
                if isinstance(consolidation, dict)
                else None,
            }

        for key, value in node.items():
            if str(key).lower() in RUN_DEFLECTION_KEYS and isinstance(value, dict):
                total = _as_int(_first(value, RUN_DEFLECTION_VALUE_KEYS))
                if total is not None:
                    return {
                        "total": total,
                        "logic": _as_text(
                            value.get("logic")
                            or value.get("method")
                            or value.get("explanation")
                        ),
                    }
            found = _find_run_deflection(value, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_run_deflection(item, depth + 1)
            if found:
                return found
    return None


def _normalise_class(raw: dict, source: dict) -> dict | None:
    """Map one Operator-emitted class onto the shape the UI renders.

    Returns None when the object carries no usable volume — a class we cannot
    size cannot be ranked, and inventing a size would be worse than omitting it.
    """
    volume = _as_int(_first(raw, FIELD_ALIASES["volume"]))
    members = _first(raw, FIELD_ALIASES["members"])
    if volume is None and isinstance(members, list):
        volume = len(members)
    if volume is None or volume <= 0:
        return None

    label = _as_text(_first(raw, FIELD_ALIASES["label"]))
    key = _as_text(_first(raw, FIELD_ALIASES["key"])) or label

    classification = _as_text(_first(raw, FIELD_ALIASES["classification"]))
    if classification:
        classification = classification.strip().upper().replace(" ", "_")

    breaches = _as_int(_first(raw, FIELD_ALIASES["breaches"]))
    poor_csat = _as_int(_first(raw, FIELD_ALIASES["poor_csat_count"]))
    avg_csat = _as_number(_first(raw, FIELD_ALIASES["avg_csat"]))
    handling_hours = _as_number(_first(raw, FIELD_ALIASES["handling_hours"]))
    reporters = _as_int(_first(raw, FIELD_ALIASES["distinct_reporters"]))
    forecast = _as_int(_first(raw, FIELD_ALIASES["deflection_forecast"]))

    kb_raw = _first(raw, FIELD_ALIASES["has_kb_article"])
    has_kb = kb_raw if isinstance(kb_raw, bool) else None
    if has_kb is None and isinstance(kb_raw, str):
        has_kb = kb_raw.strip().lower() in ("true", "yes", "matched", "found")

    languages = _first(raw, FIELD_ALIASES["languages"])
    if isinstance(languages, str):
        languages = [languages]
    elif not isinstance(languages, list):
        languages = None

    member_keys = members if isinstance(members, list) else None

    return {
        "key": key or "unlabelled-class",
        "label": label or key or "Unlabelled class",
        "classification": classification,
        "volume": volume,
        "distinct_reporters": reporters,
        "breaches": breaches,
        "poor_csat_count": poor_csat,
        "avg_csat": round(avg_csat, 2) if avg_csat is not None else None,
        "handling_hours": round(handling_hours, 1) if handling_hours is not None else None,
        "has_kb_article": has_kb,
        "proposed_fix": _as_text(_first(raw, FIELD_ALIASES["proposed_fix"])),
        "owning_team": _as_text(_first(raw, FIELD_ALIASES["owning_team"])),
        "deflection_forecast": forecast,
        "languages": languages,
        "member_keys": member_keys[:50] if member_keys else None,
        "member_count_shown": min(len(member_keys), 50) if member_keys else None,
        "needs_approval": bool(classification and classification in NEEDS_APPROVAL),
        "source": source,
        "raw": raw,
    }


def _score(entry: dict) -> dict:
    """Rank a class by the damage it does. Returns the score and its components.

    The formula is deliberately transparent, and every component is reported
    alongside the total so the ranking can be defended rather than trusted:

        impact = volume x (1 + breach_rate) x (1 + csat_damage)

    Missing inputs contribute nothing rather than being filled with an assumed
    average. A class with no CSAT data is not treated as a class with good CSAT
    — it simply scores on the evidence that exists, and the gap is reported.
    """
    volume = entry["volume"]
    breaches = entry["breaches"]
    poor_csat = entry["poor_csat_count"]
    avg_csat = entry["avg_csat"]

    breach_rate = (breaches / volume) if breaches is not None and volume else 0.0
    breach_rate = min(breach_rate, 1.0)

    # Two ways a class can show satisfaction damage. Prefer the explicit count of
    # poor scores; fall back to the average against a 5-point scale.
    if poor_csat is not None and volume:
        csat_damage = min(poor_csat / volume, 1.0)
    elif avg_csat is not None:
        csat_damage = max(0.0, min((5.0 - avg_csat) / 4.0, 1.0))
    else:
        csat_damage = 0.0

    impact = volume * (1 + breach_rate) * (1 + csat_damage)

    missing = [
        name
        for name, value in (
            ("breaches", breaches),
            ("csat", poor_csat if poor_csat is not None else avg_csat),
            ("handling_hours", entry["handling_hours"]),
        )
        if value is None
    ]

    return {
        "impact_score": round(impact, 1),
        "components": {
            "volume": volume,
            "breach_rate": round(breach_rate, 3),
            "csat_damage": round(csat_damage, 3),
            "handling_hours": entry["handling_hours"],
        },
        "missing_inputs": missing,
    }


def build_backlog(db: Session, limit: int = 25) -> dict:
    """Assemble the Elimination Backlog from mirrored Operator output."""
    activities = (
        db.query(AgentActivity, AgentRun)
        .join(AgentRun, AgentActivity.run_id == AgentRun.id)
        .order_by(AgentRun.auto_created_at.desc().nullslast())
        .all()
    )

    # Only the newest run per workflow contributes. Re-running an Operator after
    # a prompt change renames its clusters, so keeping every run would show the
    # same tickets twice under different labels and report a total larger than
    # the dataset. A later run supersedes the earlier one entirely.
    from ..models.agent import AgentWorkflow

    workflow_names = {w.auto_id: w.name for w in db.query(AgentWorkflow).all()}

    newest_run_per_workflow: dict[str, str] = {}
    for _activity, run in activities:
        wf = run.workflow_name or run.auto_workflow_id or "unknown"
        if wf not in newest_run_per_workflow:
            newest_run_per_workflow[wf] = run.auto_run_id
    accepted_runs = set(newest_run_per_workflow.values())

    superseded_runs: set[str] = set()
    by_key: dict[str, dict] = {}
    contributing_runs: set[str] = set()
    warnings: list[str] = []
    reported_deflection: dict | None = None

    for activity, run in activities:
        # A step's findings may be inline, or in a JSON report file that the
        # sync downloaded. Both are searched — Auto chooses between them based
        # on payload size, so relying on either alone loses data silently.
        payloads = [_parse_output(activity.outputs)]
        if activity.artifact_data:
            payloads.extend(activity.artifact_data.values())

        collections: list[tuple[str, list]] = []
        for payload in payloads:
            if payload is None:
                continue
            found_here = _find_class_collections(payload)
            if found_here and run.auto_run_id not in accepted_runs:
                superseded_runs.add(run.auto_run_id)
                continue
            collections.extend(found_here)
            if reported_deflection is None and run.auto_run_id in accepted_runs:
                found = _find_run_deflection(payload)
                if found is not None:
                    reported_deflection = {
                        **found,
                        "auto_run_id": run.auto_run_id,
                        "workflow_name": run.workflow_name,
                    }

        for collection_name, collection in collections:
            source = {
                "auto_run_id": run.auto_run_id,
                "workflow_name": run.workflow_name
                or workflow_names.get(run.auto_workflow_id),
                "step_name": activity.step_name,
                "collection": collection_name,
                "run_started_at": run.auto_created_at.isoformat()
                if run.auto_created_at
                else None,
            }
            for raw in collection:
                entry = _normalise_class(raw, source)
                if entry is None:
                    continue
                if entry["key"] not in by_key:
                    by_key[entry["key"]] = entry
                    contributing_runs.add(run.auto_run_id)

    # Several Operators legitimately describe the same tickets from different
    # angles — the Correlator clusters by root cause, the CSAT loop groups by
    # satisfaction damage, and the Orchestrator relays the Correlator's output
    # as part of its own. Merging them counts the same ticket several times and
    # produced a backlog larger than the dataset.
    #
    # So one source is canonical and the rest are reported alongside, never
    # summed. Deciding which class in set A equals which class in set B is a
    # judgement about meaning — that belongs to an Operator on Auto, not here.
    grouped: dict[tuple, list[dict]] = {}
    for entry in by_key.values():
        src = entry["source"]
        grouped.setdefault(
            (src["auto_run_id"], src["workflow_name"], src["collection"]), []
        ).append(entry)

    other_sources: list[dict] = []
    entries: list[dict] = []

    if grouped:
        def _coverage(items: list[dict]) -> int:
            return sum(i["volume"] for i in items)

        def _actionable(items: list[dict]) -> int:
            # Classes carrying a proposed permanent fix. This panel exists to
            # answer "what would make this stop happening", so a set that names
            # the fix is worth more than one that only sizes the problem.
            return sum(1 for i in items if i.get("proposed_fix"))

        # Widest coverage first, then whichever set actually proposes fixes.
        primary_key = max(
            grouped,
            key=lambda k: (
                _coverage(grouped[k]),
                _actionable(grouped[k]),
                len(grouped[k]),
            ),
        )
        entries = grouped[primary_key]

        for key, items in grouped.items():
            if key == primary_key:
                continue
            other_sources.append(
                {
                    "auto_run_id": key[0],
                    "workflow_name": key[1],
                    "collection": key[2],
                    "classes": len(items),
                    "tickets": _coverage(items),
                }
            )

    for entry in entries:
        entry.update(_score(entry))
    entries.sort(key=lambda e: e["impact_score"], reverse=True)

    # Deflection: tickets that stop needing individual handling. Only counted
    # where an Operator actually said so — never inferred from cluster size,
    # because collapsing a cluster is a decision the agent makes, not us.
    forecast_total = sum(
        e["deflection_forecast"] for e in entries if e["deflection_forecast"] is not None
    )
    classes_with_forecast = sum(
        1 for e in entries if e["deflection_forecast"] is not None
    )
    total_volume = sum(e["volume"] for e in entries)

    if not entries:
        warnings.append(
            "No Operator has emitted ticket-class data yet. Run the "
            "Major-Incident Correlator or the CSAT and Knowledge Loop Operator "
            "on Supervity Auto, then sync."
        )
    if entries and classes_with_forecast == 0 and reported_deflection is None:
        warnings.append(
            "No class carries a deflection forecast. The Operators are "
            "reporting classes but not yet forecasting prevented tickets."
        )
    if entries and classes_with_forecast == 0 and reported_deflection is not None:
        warnings.append(
            "Deflection is reported once for the whole run rather than per "
            "class, so the ranked list below cannot attribute it to individual "
            "classes. The run-level figures are shown exactly as the Operator "
            "reported them."
        )

    awaiting = [e for e in entries if e["needs_approval"]]

    if superseded_runs:
        warnings.append(
            f"{len(superseded_runs)} earlier run(s) also reported classes and "
            "were superseded by the newest run of the same workflow."
        )

    if other_sources:
        total_other = sum(s["classes"] for s in other_sources)
        warnings.append(
            f"{total_other} class(es) from {len(other_sources)} other Operator "
            "view(s) are not shown. They describe the same tickets from a "
            "different angle, and adding them would count tickets twice."
        )

    return {
        "has_data": bool(entries),
        "generated_from_runs": sorted(contributing_runs),
        "superseded_runs": sorted(superseded_runs),
        # Reported, never merged into the totals above.
        "other_sources": other_sources,
        "totals": {
            "classes": len(entries),
            "tickets_in_classes": total_volume,
            "deflection_forecast": forecast_total,
            "classes_with_forecast": classes_with_forecast,
            "awaiting_approval": len(awaiting),
            # Share of classified tickets an Operator expects to prevent.
            "deflection_rate_pct": round(100.0 * forecast_total / total_volume, 1)
            if total_volume and forecast_total
            else None,
        },
        # The agent's own run-level figure, with its stated method, kept
        # distinct from the per-class forecasts above.
        "reported_deflection": reported_deflection,
        "classes": entries[:limit],
        "truncated": max(len(entries) - limit, 0),
        "warnings": warnings,
    }
