"""
Data Manager — live integration health.

The registry is discovered from the workflows on Supervity Auto rather than
declared here, so connecting a new system in Auto surfaces it without a code
change.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import integrations as integrations_service
from ..services.supervity import SupervityClient, get_supervity_client

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("")
async def list_integrations(
    db: Session = Depends(get_db),
    client: SupervityClient = Depends(get_supervity_client),
):
    """Every integration the Command Center depends on, with its health.

    `check_type` distinguishes a live probe from health inferred out of recent
    agent runs — the OneDrive, GitHub and Outlook connections belong to the
    Operators on Auto, so there is nothing here to probe directly and the
    response says so rather than implying otherwise.
    """
    return await integrations_service.build_registry(db, client)
