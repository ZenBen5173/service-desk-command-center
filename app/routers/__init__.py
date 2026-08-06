# app/routers/__init__.py
"""
API Routers - Modular endpoint organization.

Note: File endpoints are defined in main.py to maintain proper path ordering.
"""

from .admin import router as admin_router
from .agent import router as agent_router
from .audit import router as audit_router
from .business import router as business_router
from .auth import router as auth_router
from .elimination import router as elimination_router
from .examples import router as examples_router
from .health import router as health_router
from .insights import router as insights_router
from .integrations import router as integrations_router
from .manager import router as manager_router
from .policies import router as policies_router
from .workbench import router as workbench_router
from .items import router as items_router

__all__ = [
    "health_router",
    "auth_router",
    "admin_router",
    "audit_router",
    "items_router",
    "examples_router",
    "agent_router",
    "elimination_router",
    "policies_router",
    "workbench_router",
    "integrations_router",
    "business_router",
    "insights_router",
    "manager_router",
]
