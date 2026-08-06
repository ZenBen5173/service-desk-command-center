"""
AI Insights — patterns, anomalies and recommendations from the operation.

Assembled from findings the Operators reported on Supervity Auto. Nothing is
inferred here that an agent did not observe.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import insights as insights_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("")
def list_insights(db: Session = Depends(get_db)):
    """Recurring clusters, forming incidents, knowledge gaps, SLA forecast, team load."""
    return insights_service.collect(db)
