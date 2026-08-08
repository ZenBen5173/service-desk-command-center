# app/main.py
"""
FastAPI Application Entry Point

This is the main application file that:
- Creates the FastAPI app instance
- Configures CORS middleware
- Configures Audit middleware (automatic request/response logging)
- Registers all API routers
- Sets up the authorization middleware

All endpoint logic has been organized into routers:
- routers/health.py - Health checks
- routers/auth.py - Authentication & registration
- routers/admin.py - Admin user management & settings
- routers/items.py - Item CRUD operations
- routers/audit.py - Audit log viewing & export
- routers/examples.py - Authorization pattern examples

AUDIT SYSTEM:
- Every API request is automatically logged via AuditMiddleware
- Custom audit logging available via `from app.services.audit import audit`
- View logs at /api/admin/audit, export via /api/admin/audit/export
- See app/models/audit.py for full documentation
"""

import io
import logging
import os

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .authz import AuthzEngine
from .core.storage import GCSStorage, LocalStorage, StorageBackend
from .middleware import AuditMiddleware
from .routers import (
    admin_router,
    agent_router,
    audit_router,
    auth_router,
    business_router,
    elimination_router,
    examples_router,
    health_router,
    insights_router,
    integrations_router,
    items_router,
    manager_router,
    policies_router,
    workbench_router,
)
from .security import get_current_user, verify_access

log = logging.getLogger(__name__)

# =============================================================================
# BASE PATH CONFIGURATION
# =============================================================================

# Get BASE_PATH from environment (e.g., "/app1" or empty string)
# This allows the API to be mounted at a subpath
BASE_PATH = os.getenv("BASE_PATH", "")
if BASE_PATH and not BASE_PATH.startswith("/"):
    BASE_PATH = f"/{BASE_PATH}"
if BASE_PATH == "/":
    BASE_PATH = ""

log.info(f"API Base Path: '{BASE_PATH}' (empty means root)")

# =============================================================================
# APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="AutoPilot API",
    description="AI Command Center — Full-stack template with FastAPI, Next.js, and PostgreSQL",
    version="2.0.0",
    docs_url=f"{BASE_PATH}/api/docs",
    redoc_url=f"{BASE_PATH}/api/redoc",
    openapi_url=f"{BASE_PATH}/api/openapi.json",
)

# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================

# CORS Middleware
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3001")
cors_origins = [
    frontend_url,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit Middleware - Automatic request/response logging
# This middleware logs ALL HTTP requests to the database for compliance & debugging.
# Disable by setting AUDIT_MIDDLEWARE_ENABLED=false in environment.
# See app/middleware/audit.py for configuration options.
app.add_middleware(AuditMiddleware)

# =============================================================================
# API ROUTER WITH AUTHORIZATION
# =============================================================================

# Create main API router with global authorization middleware
# The prefix includes BASE_PATH so routes are at {BASE_PATH}/api/...
api_router = APIRouter(
    prefix=f"{BASE_PATH}/api",
    dependencies=[Depends(verify_access)],
)

# =============================================================================
# STORAGE DEPENDENCY
# =============================================================================


def get_storage_dependency() -> StorageBackend:
    """Get the appropriate storage backend based on environment."""
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "gcs":
        bucket = os.getenv("GCS_BUCKET")
        prefix = os.getenv("GCS_PREFIX", "")
        if not bucket:
            raise ValueError("GCS_BUCKET environment variable is required")
        return GCSStorage(bucket, prefix)
    else:
        path = os.getenv("LOCAL_STORAGE_PATH", "./document_storage")
        return LocalStorage(path)


# =============================================================================
# INCLUDE ROUTERS
# =============================================================================

# Health checks (public)
api_router.include_router(health_router)

# Authentication & registration
api_router.include_router(auth_router)

# Admin user management & settings
api_router.include_router(admin_router)

# Audit logs (admin only)
api_router.include_router(audit_router)

# Item CRUD operations
api_router.include_router(items_router)

# Authorization pattern examples
api_router.include_router(examples_router)

# Live agent activity mirrored from Supervity Auto
api_router.include_router(agent_router)

# Elimination Backlog — ranked ticket classes from Operator findings
api_router.include_router(elimination_router)

# AI Policies — editable governance rules and their evaluation log
api_router.include_router(policies_router)

# Workbench — human-in-the-loop queue for agent escalations
api_router.include_router(workbench_router)

# Data Manager — live integration registry and health
api_router.include_router(integrations_router)

# Business outcome metrics — the judged figures
api_router.include_router(business_router)

# AI Insights — observations drawn from Operator findings
api_router.include_router(insights_router)

# AI Manager — question-and-answer over the operation
api_router.include_router(manager_router)


# =============================================================================
# FILE STORAGE ENDPOINTS (kept inline for path matching order)
# =============================================================================


@api_router.get("/files/", tags=["Files"])
async def list_files(
    prefix: str = "",
    storage: StorageBackend = Depends(get_storage_dependency),
    user: dict = Depends(get_current_user),
):
    """List all files in storage, optionally filtered by prefix."""
    files = await storage.list_files(prefix)
    return {"files": files, "count": len(files)}


@api_router.post("/files/{file_path:path}", tags=["Files"])
async def upload_file(
    file_path: str,
    file: UploadFile = File(...),
    storage: StorageBackend = Depends(get_storage_dependency),
    user: dict = Depends(get_current_user),
):
    """Upload a file to storage."""
    content = await file.read()
    url = await storage.save(file_path, content, file.content_type)
    return {
        "path": file_path,
        "url": url,
        "content_type": file.content_type,
        "size": len(content),
    }


@api_router.get("/files/{file_path:path}", tags=["Files"])
async def download_file(
    file_path: str,
    storage: StorageBackend = Depends(get_storage_dependency),
    user: dict = Depends(get_current_user),
):
    """Download a file from storage."""
    try:
        content, content_type = await storage.load(file_path)
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{file_path}"'},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@api_router.delete("/files/{file_path:path}", tags=["Files"])
async def delete_file(
    file_path: str,
    storage: StorageBackend = Depends(get_storage_dependency),
    user: dict = Depends(get_current_user),
):
    """Delete a file from storage."""
    await storage.delete(file_path)
    return {"status": "deleted", "path": file_path}


# =============================================================================
# MOUNT ROUTERS TO APP
# =============================================================================

app.include_router(api_router)


# =============================================================================
# BACKGROUND SYNC
# =============================================================================
#
# The pages poll this database every thirty seconds, but nothing pulled from
# Supervity Auto unless somebody clicked Sync. A dashboard left open showed
# whatever was true when it was last clicked, and during a demo nobody is
# clicking. This keeps the mirror current on its own.


@app.on_event("startup")
async def _start_background_sync() -> None:
    from .services import autosync

    autosync.start()


# =============================================================================
# ROOT ENDPOINT
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "name": "AutoPilot API",
        "version": "2.0.0",
        "docs": f"{BASE_PATH}/api/docs",
        "health": f"{BASE_PATH}/api/health",
        "base_path": BASE_PATH or "/",
    }


# Also mount root at BASE_PATH if configured
if BASE_PATH:

    @app.get(BASE_PATH)
    async def base_path_root():
        """Base path root endpoint - API information."""
        return {
            "name": "AutoPilot API",
            "version": "2.0.0",
            "docs": f"{BASE_PATH}/api/docs",
            "health": f"{BASE_PATH}/api/health",
            "base_path": BASE_PATH,
        }
