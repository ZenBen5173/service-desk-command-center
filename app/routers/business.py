"""
Business outcome metrics — the figures this project is judged on.

Read straight from what the Operators reported on Supervity Auto. A metric no
Operator has produced comes back null with a note, never as a zero.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import business_metrics

log = logging.getLogger(__name__)

router = APIRouter(prefix="/business", tags=["Business"])


@router.get("/metrics")
def get_business_metrics(db: Session = Depends(get_db)):
    """MTTR, SLA compliance, auto-resolution rate, CSAT, and deflection.

    Each value carries the workflow that produced it in `sources`, so any
    number on screen can be traced back to a specific agent run.
    """
    return business_metrics.collect(db)
