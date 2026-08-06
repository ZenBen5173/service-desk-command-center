"""
Workbench — where work the agent refused to do alone lands in front of a human.

The requirement is a real exception, carrying full context, resolved here. So
these rows are only ever created from something an Operator on Supervity Auto
actually escalated. Nothing is seeded, and nothing is invented to make the queue
look busy: an empty Workbench means the agent handled everything it saw, which
is a fact worth showing rather than hiding.

A resolution recorded here is the human's decision. It is deliberately stored
alongside the agent's own recommendation so the two can be compared — including
when the human overrode the agent.
"""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from ..core.database import Base


class WorkbenchException(Base):
    """One item awaiting, or having received, a human decision."""

    __tablename__ = "workbench_exceptions"

    id = Column(Integer, primary_key=True, index=True)

    # Stable identity so repeated syncs update rather than duplicate. Derived
    # from the originating activity plus the subject it concerns.
    dedupe_key = Column(String(256), unique=True, nullable=False, index=True)

    # What kind of thing needs a human: low confidence, policy conflict, missing
    # evidence, change approval, repeat failure, identity ambiguity.
    exception_type = Column(String(64), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    subject_ref = Column(String(128), nullable=True, index=True)
    subject_type = Column(String(64), nullable=True)

    # Why the agent stopped, in its own words.
    reason = Column(Text, nullable=True)
    # What the agent would have done had it been allowed to proceed.
    agent_recommendation = Column(Text, nullable=True)
    agent_confidence = Column(Float, nullable=True)
    # Everything the human needs to decide without leaving the page.
    context = Column(JSON, nullable=True)

    priority = Column(String(32), nullable=True, index=True)

    # Provenance back to the exact agent run and step that raised it.
    auto_run_id = Column(String(64), nullable=True, index=True)
    workflow_name = Column(String(255), nullable=True)
    step_name = Column(String(255), nullable=True)
    activity_id = Column(
        Integer, ForeignKey("agent_activities.id"), nullable=True, index=True
    )

    status = Column(String(32), nullable=False, default="open", index=True)
    # "approve" | "reject" | "modify" | "more_info"
    resolution = Column(String(32), nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    raised_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_payload = Column(JSON, nullable=True)

    def __repr__(self):
        return (
            f"<WorkbenchException(subject='{self.subject_ref}', "
            f"status='{self.status}')>"
        )


# The queue is read open-first, newest-first, on every page load.
Index(
    "ix_workbench_status_raised",
    WorkbenchException.status,
    WorkbenchException.raised_at,
)
