"""
AI Manager — a chat surface over the operation.

Answers are assembled from mirrored agent data and cite the Operator they came
from. Nothing is paraphrased by a language model, because a summary that drifts
from the audit record is the exact failure this project set out to avoid.
"""

import logging

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import manager as manager_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/manager", tags=["Manager"])


@router.post("/ask")
def ask(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Answer a question about the operation from real agent data."""
    return manager_service.answer(db, str(payload.get("question", "")))
