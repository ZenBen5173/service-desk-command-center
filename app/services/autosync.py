"""
Keep the mirror current without anyone pressing a button.

Every page in the Command Center re-reads this database every thirty seconds,
so the screen is always current with what we hold. What was missing is the step
before that: pulling from Supervity Auto. Until now that only happened when
someone clicked "Sync from Auto", which means a dashboard left open showed
whatever was true when it was last clicked — and during a demo, nobody is
clicking.

This runs the same sync on a timer. It is the only thing in this repository
that acts on its own, so it is deliberately narrow: it reads from Auto, writes
to the mirror, and does nothing else. It never triggers an agent, never decides
anything, and never sends anything outward.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Long enough that a demo never waits on it, short enough that Auto is not
# polled harder than it needs to be. Auto rate-limits at 60 requests a minute
# and a full sync costs far fewer than that.
DEFAULT_INTERVAL_SECONDS = 180

# Timelines are one request each, so a periodic sync fetches only what is new.
# The pending count is reported by the sync itself, so nothing is lost silently.
DEFAULT_TIMELINE_LIMIT = 15

_state: dict = {
    "enabled": False,
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_error": None,
    "syncs_completed": 0,
    "interval_seconds": DEFAULT_INTERVAL_SECONDS,
}


def status() -> dict:
    """What the background sync has been doing, for the UI to show honestly."""
    return dict(_state)


async def _sync_once() -> None:
    # Imported here rather than at module level: this module is loaded during
    # app startup, before the database engine is necessarily ready.
    from ..core.database import SessionLocal
    from ..services import agent_sync
    from ..services.supervity import (
        SupervityError,
        SupervityNotConfigured,
        get_supervity_client,
    )

    db = SessionLocal()
    try:
        client = get_supervity_client()
        _state["last_started_at"] = datetime.now(timezone.utc).isoformat()
        result = await agent_sync.sync_all(
            db, client, timeline_limit=DEFAULT_TIMELINE_LIMIT
        )
        _state["last_finished_at"] = datetime.now(timezone.utc).isoformat()
        _state["syncs_completed"] += 1
        # Errors inside a sync are collected rather than raised, so surface them
        # instead of reporting a clean run that quietly failed in the middle.
        errors = result.get("errors") or []
        _state["last_error"] = "; ".join(str(e) for e in errors)[:400] or None
    except SupervityNotConfigured as exc:
        _state["last_error"] = str(exc)
        log.info("Background sync idle: %s", exc)
    except SupervityError as exc:
        _state["last_error"] = str(exc)[:400]
        log.warning("Background sync could not reach Auto: %s", exc)
    finally:
        db.close()


async def _loop(interval: int) -> None:
    # A first sync straight away, so a cold start is current rather than waiting
    # out a full interval with an empty screen.
    while True:
        try:
            await _sync_once()
        except Exception as exc:  # noqa: BLE001 - the loop must outlive any one failure
            _state["last_error"] = f"{type(exc).__name__}: {exc}"[:400]
            log.exception("Background sync failed")
        await asyncio.sleep(interval)


def start() -> None:
    """Begin syncing on a timer, unless switched off.

    Set AUTO_SYNC_ENABLED=false to stop it — useful when demonstrating that a
    number changed because of something you did, rather than because a sync
    happened to land mid-sentence.
    """
    if os.getenv("AUTO_SYNC_ENABLED", "true").strip().lower() in ("false", "0", "no"):
        log.info("Background sync disabled by AUTO_SYNC_ENABLED")
        return
    if _state["running"]:
        return

    try:
        interval = max(60, int(os.getenv("AUTO_SYNC_SECONDS", DEFAULT_INTERVAL_SECONDS)))
    except ValueError:
        interval = DEFAULT_INTERVAL_SECONDS

    _state.update({"enabled": True, "running": True, "interval_seconds": interval})
    asyncio.create_task(_loop(interval))
    log.info("Background sync started, every %ds", interval)
