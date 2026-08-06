"""
Supervity Auto API client.

The Orchestrator and every Operator live on Auto (auto.supervity.ai). This module
only *reads* what Auto did and *triggers* runs — it never reimplements agent
logic. That separation is a hard rule for this project.

A note on the base URL: the published docs point at hosts that do not serve the
API. The working host is `auto-workflow-api.supervity.ai`, discovered from the
content-security-policy header that auto.supervity.ai returns. Requests to the
other hosts answer 400 "Unexpected Server Error" no matter what you send.

Auth is a bearer token plus `x-source: external`. Omitting `x-source` gives a
flat 401 even with a valid key.
"""

import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://auto-workflow-api.supervity.ai"
API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 60.0


class SupervityError(RuntimeError):
    """Raised when Auto is unreachable, unauthorised, or answers unusably."""


class SupervityNotConfigured(SupervityError):
    """Raised when no API key is present. Distinct so the UI can say so plainly."""


class SupervityClient:
    """Thin async wrapper over the Auto workflow API.

    Deliberately thin: it returns Auto's payloads close to untouched so the
    Command Center can surface authoritative JSON. Round 1 showed that Auto's
    natural-language summaries contradict its own activity timeline — inventing
    ticket numbers, identities and confidence values. The timeline is the record
    of what happened; the prose is not. Nothing here should ever paraphrase a
    run, and callers should prefer activity outputs over any summary text.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("SUPERVITY_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("SUPERVITY_API_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise SupervityNotConfigured(
                "SUPERVITY_API_KEY is not set. Add it to .env and restart the backend."
            )
        return {
            "Authorization": f"Bearer {self.api_key}",
            # Required for custom API keys. Without it every call 401s.
            "x-source": "external",
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.base_url}{API_PREFIX}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=self._headers(), params=params)
        except httpx.RequestError as exc:
            raise SupervityError(f"Could not reach Auto at {url}: {exc}") from exc

        if resp.status_code == 401:
            raise SupervityError(
                "Auto rejected the API key (401). It may have been revoked or "
                "regenerated at auto.supervity.ai/u/api-keys."
            )
        if resp.status_code >= 400:
            raise SupervityError(
                f"Auto returned {resp.status_code} for {path}: {resp.text[:300]}"
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise SupervityError(
                f"Auto returned non-JSON for {path}: {resp.text[:200]}"
            ) from exc

    # ------------------------------------------------------------------
    # Workflows — the Orchestrator and Operators as they exist on Auto
    # ------------------------------------------------------------------

    async def list_workflows(self, limit: int = 100, page: int = 1) -> list[dict]:
        # Deliberately no isDraft filter. Auto returns the same rows for
        # isDraft=true and isDraft=false, and passing it surfaced workflows the
        # user had already deleted — which inflated the Operator count. The
        # unfiltered list matches what the Operators page actually shows.
        data = await self._get("/workflows", {"limit": min(limit, 100), "page": page})
        # Auto has returned both a bare list and a wrapped object across versions.
        if isinstance(data, list):
            return data
        return data.get("workflows", [])

    async def get_workflow(self, workflow_id: str) -> dict:
        return await self._get(f"/workflows/{workflow_id}")

    # ------------------------------------------------------------------
    # Runs — what the agents actually did
    # ------------------------------------------------------------------

    async def list_runs(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> tuple[list[dict], dict]:
        """Return (runs, pagination). Pagination is passed through untouched."""
        params: dict[str, Any] = {"limit": min(limit, 100), "page": page}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        data = await self._get("/workflow-runs", params)
        if isinstance(data, list):
            return data, {}
        return data.get("workflowRuns", []), data.get("pagination", {})

    async def get_run(self, run_id: str) -> dict:
        """One run plus its activity timeline.

        Shape: {"workflowRun": {...}, "activityRuns": [...]}. The activityRuns
        array is the authoritative step-by-step record — per-step status, outputs,
        timings, retry attempt and error details.
        """
        return await self._get(f"/workflow-runs/{run_id}")

    async def get_dashboard(self, workflow_id: str) -> dict:
        """Auto's own run-count breakdown by status for one workflow."""
        return await self._get(f"/workflow-runs/dashboard/{workflow_id}")

    # ------------------------------------------------------------------
    # Triggering
    # ------------------------------------------------------------------

    async def execute(
        self,
        workflow_id: str,
        inputs: dict | None = None,
        envs: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        """Run a workflow and block until it finishes.

        Sent as multipart/form-data with `inputs` JSON-encoded — that is what the
        endpoint expects, not a JSON body.
        """
        import json as _json

        url = f"{self.base_url}{API_PREFIX}/workflow-runs/execute"
        form: dict[str, str] = {"workflowId": workflow_id}
        if inputs:
            form["inputs"] = _json.dumps(inputs)
        if envs:
            form["envs"] = _json.dumps(envs)

        try:
            async with httpx.AsyncClient(timeout=timeout or 900.0) as client:
                resp = await client.post(url, headers=self._headers(), data=form)
        except httpx.RequestError as exc:
            raise SupervityError(f"Could not reach Auto at {url}: {exc}") from exc

        if resp.status_code >= 400:
            raise SupervityError(
                f"Auto returned {resp.status_code} executing {workflow_id}: "
                f"{resp.text[:300]}"
            )
        return resp.json()

    async def fetch_artifact(self, url: str, max_bytes: int = 8_000_000) -> Any:
        """Download a step's output file and parse it as JSON.

        Auto writes larger step reports to object storage and returns a signed
        URL that expires, so the content is pulled once at sync time. Returns
        None for anything that is not JSON or is too large to be a report —
        those are not errors, just not something the Command Center can read.
        """
        import json as _json

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
        except httpx.RequestError as exc:
            log.warning("Could not download artifact: %s", exc)
            return None

        if resp.status_code >= 400:
            log.warning("Artifact download returned %s", resp.status_code)
            return None
        if len(resp.content) > max_bytes:
            log.warning("Artifact is %d bytes, skipping", len(resp.content))
            return None

        try:
            return _json.loads(resp.content)
        except (ValueError, UnicodeDecodeError):
            return None

    async def health(self) -> dict:
        """Cheap reachability probe used by the Data Manager integration panel."""
        if not self.is_configured:
            return {
                "healthy": False,
                "detail": "SUPERVITY_API_KEY is not set",
                "base_url": self.base_url,
            }
        try:
            workflows = await self.list_workflows(limit=1)
        except SupervityError as exc:
            return {"healthy": False, "detail": str(exc), "base_url": self.base_url}
        return {
            "healthy": True,
            "detail": f"reachable, {len(workflows)} workflow(s) visible on this page",
            "base_url": self.base_url,
        }


def get_supervity_client() -> SupervityClient:
    """FastAPI dependency. Reads env at call time so a restart picks up key changes."""
    return SupervityClient()
