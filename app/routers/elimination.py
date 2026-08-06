"""
Elimination Backlog endpoints.

Reads ticket-class findings that Operators produced on Supervity Auto, ranks
them by damage, and reports how many tickets are forecast to be prevented.

No clustering, classification or fix-selection happens here — that is Operator
work and it stays on Auto.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import elimination

log = logging.getLogger(__name__)

router = APIRouter(prefix="/elimination", tags=["Elimination"])


@router.get("/backlog")
def get_backlog(
    limit: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Ranked classes of ticket worth eliminating, newest Operator run wins.

    `has_data` is false when no Operator has emitted class findings yet. The UI
    must show that state rather than an empty-looking backlog, because an empty
    backlog and an unrun agent mean very different things.
    """
    return elimination.build_backlog(db, limit=limit)
