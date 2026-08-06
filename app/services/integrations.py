"""
Data Manager — the live integration registry.

Which systems this Command Center actually depends on, and whether each one is
healthy. The list is discovered rather than declared: the integrations the
agents use come from the `services` each workflow on Supervity Auto reports,
so connecting a new system in Auto makes it appear here without a code change.

Health is evidence-based. Where a system can be probed directly it is probed.
Where it can only be observed through the agents — an Operator's OneDrive
access, for instance — health is derived from whether recent runs using that
service succeeded, and the answer says so rather than implying a live check.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.agent import AgentRun, AgentWorkflow
from .supervity import SupervityClient

log = logging.getLogger(__name__)

# Presentation metadata for service identifiers Auto reports. Unknown services
# still appear — they are shown with their raw key rather than being dropped,
# because a silently missing integration is worse than an unlabelled one.
SERVICE_CATALOGUE: dict[str, dict[str, str]] = {
    "microsoft_onedrive": {
        "name": "Microsoft OneDrive",
        "category": "Data Source",
        "purpose": "Source ticket, user, knowledge and change exports",
    },
    "github": {
        "name": "GitHub Issues",
        "category": "System of Record",
        "purpose": "Ticket system of record — incidents, approvals, KB drafts",
    },
    "microsoft_outlook": {
        "name": "Microsoft Outlook",
        "category": "Communication",
        "purpose": "Requester communication in their own language",
    },
    "llm": {
        "name": "Language Model",
        "category": "AI",
        "purpose": "Symptom clustering and root-cause reasoning",
    },
    "human_input_form": {
        "name": "Human Input Form",
        "category": "Human-in-the-loop",
        "purpose": "Approval gates presented to a person",
    },
    "output_artifacts": {
        "name": "Output Artifacts",
        "category": "Storage",
        "purpose": "Structured run reports the Command Center reads",
    },
}

# Auto lists a workflow's pip packages and file formats alongside its real
# connections. Those are runtime dependencies, not integrations — showing
# "pandas" next to OneDrive as a connected system would be misleading. They are
# excluded from the registry and reported separately so the filtering is visible
# rather than silent.
NON_INTEGRATION_SERVICES = {
    "pandas",
    "numpy",
    "csv",
    "json",
    "excel",
    "openpyxl",
    "xlsx",
    "requests",
    "httpx",
    "python",
    "datetime",
    "re",
    "io",
    "os",
}

# How long a successful run keeps counting as evidence that a service works.
EVIDENCE_WINDOW = timedelta(days=45)


def _humanise(service_key: str) -> dict[str, str]:
    known = SERVICE_CATALOGUE.get(service_key)
    if known:
        return known
    return {
        "name": service_key.replace("_", " ").title(),
        "category": "Other",
        "purpose": "Reported by a workflow on Supervity Auto",
    }


def _check_database(db: Session) -> dict:
    """Direct probe. The Command Center cannot work without this."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "detail": "Query succeeded",
            "check_type": "direct",
        }
    except Exception as exc:  # noqa: BLE001 - report, never crash the page
        return {
            "status": "down",
            "detail": f"Query failed: {exc}",
            "check_type": "direct",
        }


async def _check_supervity(client: SupervityClient) -> dict:
    """Direct probe of the agent platform."""
    health = await client.health()
    return {
        "status": "healthy" if health.get("healthy") else "down",
        "detail": health.get("detail") or "",
        "check_type": "direct",
    }


def _service_evidence(db: Session, service_key: str, now: datetime) -> dict:
    """Derive a service's health from agent runs that used it.

    OneDrive, GitHub and Outlook are reached by the Operators using their own
    credentials on Auto, not by this backend, so there is nothing here to probe.
    What can be said honestly is whether runs depending on that service have
    been succeeding, and how recently.
    """
    workflows = [
        w for w in db.query(AgentWorkflow).all() if service_key in (w.services or [])
    ]
    if not workflows:
        return {
            "status": "unknown",
            "detail": "No workflow on Auto declares this service",
            "check_type": "inferred",
            "workflows": [],
            "runs_in_window": 0,
        }

    auto_ids = {w.auto_id for w in workflows}
    runs = [
        r
        for r in db.query(AgentRun).all()
        if r.auto_workflow_id in auto_ids and r.auto_created_at is not None
    ]
    recent = [r for r in runs if now - r.auto_created_at <= EVIDENCE_WINDOW]

    completed = [r for r in recent if (r.status or "").lower() == "completed"]
    failed = [r for r in recent if (r.status or "").lower() in ("failed", "error")]
    last_run = max((r.auto_created_at for r in recent), default=None)

    if not recent:
        status = "unknown"
        detail = "No runs using this service inside the evidence window"
    elif failed and not completed:
        status = "down"
        detail = f"All {len(failed)} recent run(s) using this service failed"
    elif failed:
        status = "degraded"
        detail = (
            f"{len(completed)} succeeded, {len(failed)} failed "
            f"of {len(recent)} recent run(s)"
        )
    else:
        status = "healthy"
        detail = f"{len(completed)} recent run(s) using this service all succeeded"

    return {
        "status": status,
        "detail": detail,
        "check_type": "inferred",
        # Deduplicated: an Auto account can hold two workflows with the same
        # name, and listing one twice under "used by" says nothing extra.
        "workflows": sorted({w.name for w in workflows}),
        "workflow_count": len(workflows),
        "runs_in_window": len(recent),
        "runs_succeeded": len(completed),
        "runs_failed": len(failed),
        "last_used_at": last_run.isoformat() if last_run else None,
    }


async def build_registry(db: Session, client: SupervityClient) -> dict:
    """Assemble the live integration registry."""
    now = datetime.now(timezone.utc)
    integrations: list[dict] = []

    # --- Directly probed -------------------------------------------------
    supervity = await _check_supervity(client)
    integrations.append(
        {
            "key": "supervity_auto",
            "name": "Supervity Auto",
            "category": "Agent Platform",
            "purpose": "Runs the Orchestrator and every Operator",
            "endpoint": client.base_url,
            "checked_at": now.isoformat(),
            **supervity,
        }
    )

    database = _check_database(db)
    integrations.append(
        {
            "key": "postgres",
            "name": "PostgreSQL",
            "category": "Database",
            "purpose": "Mirrors agent activity, policies, and the Workbench queue",
            "endpoint": os.getenv("POSTGRES_HOST", "postgres"),
            "checked_at": now.isoformat(),
            **database,
        }
    )

    # --- Discovered from the workflows on Auto ---------------------------
    service_keys: set[str] = set()
    excluded: set[str] = set()
    for workflow in db.query(AgentWorkflow).all():
        for service in workflow.services or []:
            if str(service).lower() in NON_INTEGRATION_SERVICES:
                excluded.add(str(service))
            else:
                service_keys.add(service)

    for service_key in sorted(service_keys):
        meta = _humanise(service_key)
        evidence = _service_evidence(db, service_key, now)
        integrations.append(
            {
                "key": service_key,
                "name": meta["name"],
                "category": meta["category"],
                "purpose": meta["purpose"],
                "endpoint": None,
                "checked_at": now.isoformat(),
                **evidence,
            }
        )

    categories = sorted({i["category"] for i in integrations})
    healthy = [i for i in integrations if i["status"] == "healthy"]

    warnings: list[str] = []
    if len(integrations) < 3:
        warnings.append(
            "Fewer than three integrations are visible. Connect the services in "
            "Supervity Auto and sync — this list is discovered, not declared."
        )
    if len(categories) < 2:
        warnings.append("Integrations span fewer than two categories.")

    return {
        "integrations": sorted(
            integrations, key=lambda i: (i["category"], i["name"])
        ),
        "totals": {
            "count": len(integrations),
            "healthy": len(healthy),
            "degraded": sum(1 for i in integrations if i["status"] == "degraded"),
            "down": sum(1 for i in integrations if i["status"] == "down"),
            "unknown": sum(1 for i in integrations if i["status"] == "unknown"),
            "categories": len(categories),
        },
        "categories": categories,
        "evidence_window_days": EVIDENCE_WINDOW.days,
        # Runtime dependencies Auto reports alongside real connections. Listed
        # so the filtering is auditable rather than invisible.
        "excluded_as_libraries": sorted(excluded),
        "generated_at": now.isoformat(),
        "warnings": warnings,
    }
