"""
Local mirror of Supervity Auto agent activity.

Auto is the system of record for what the agents did. We copy runs and their
activity timelines into Postgres so the Command Center can render instantly,
aggregate across runs, and keep showing history if Auto is briefly unreachable
mid-demo.

Nothing here decides anything. It stores what Auto reported, verbatim, in
`raw_payload`, alongside a few extracted columns for querying.
"""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class AgentWorkflow(Base):
    """An Orchestrator or Operator as it exists on Auto."""

    __tablename__ = "agent_workflows"

    id = Column(Integer, primary_key=True, index=True)
    # Auto's UUID. Unique so repeated syncs update rather than duplicate.
    auto_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # Which integrations the workflow touches — feeds the Data Manager.
    services = Column(JSON, nullable=True)
    role = Column(String(32), nullable=True)  # "orchestrator" | "operator"
    auto_created_at = Column(DateTime(timezone=True), nullable=True)
    auto_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    runs = relationship("AgentRun", back_populates="workflow")

    def __repr__(self):
        return f"<AgentWorkflow(name='{self.name}', role='{self.role}')>"


class AgentRun(Base):
    """One execution of a workflow on Auto."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    auto_run_id = Column(String(64), unique=True, nullable=False, index=True)
    auto_workflow_id = Column(String(64), nullable=False, index=True)
    workflow_id = Column(
        Integer, ForeignKey("agent_workflows.id"), nullable=True, index=True
    )
    workflow_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=True, index=True)
    inputs = Column(JSON, nullable=True)
    # Auto's own timestamps, not ours — MTTR maths must use the agent's clock.
    auto_created_at = Column(DateTime(timezone=True), nullable=True, index=True)
    auto_updated_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    # Whether the activity timeline has been fetched for this run.
    timeline_synced_at = Column(DateTime(timezone=True), nullable=True)
    # Auto lists some older runs but 404s when their timeline is requested.
    # Recording why stops us re-requesting them on every sync, and keeps the
    # gap visible instead of silently pretending the run had no steps.
    timeline_error = Column(Text, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("AgentWorkflow", back_populates="runs")
    activities = relationship(
        "AgentActivity", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AgentRun(workflow='{self.workflow_name}', status='{self.status}')>"


class AgentActivity(Base):
    """One step within a run — Auto calls these activity runs.

    This is the authoritative record of agent behaviour. Auto's chat-style
    summaries have been observed contradicting it, so the UI reads from here.
    """

    __tablename__ = "agent_activities"

    id = Column(Integer, primary_key=True, index=True)
    auto_activity_id = Column(String(64), unique=True, nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    step_id = Column(String(128), nullable=True)
    step_name = Column(String(255), nullable=True)
    step_description = Column(Text, nullable=True)
    status = Column(String(32), nullable=True, index=True)
    kind = Column(String(32), nullable=True)
    attempt = Column(Integer, nullable=True)
    # Step outputs verbatim. This is where policy decisions, cluster assignments
    # and metrics arrive from the Operators.
    outputs = Column(JSON, nullable=True)
    # Auto often writes a step's full report to a file instead of inlining it,
    # leaving only a download link in `outputs`. These hold the file references
    # and, for JSON reports, the downloaded content — the signed URLs expire, so
    # the payload is fetched once at sync time and kept.
    output_files = Column(JSON, nullable=True)
    artifact_data = Column(JSON, nullable=True)
    error_details = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    sequence = Column(Integer, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("AgentRun", back_populates="activities")

    def __repr__(self):
        return f"<AgentActivity(step='{self.step_name}', status='{self.status}')>"


# Aggregations scan runs by time and by workflow constantly; these keep the
# dashboard responsive as run history grows over the day.
Index("ix_agent_runs_workflow_created", AgentRun.auto_workflow_id, AgentRun.auto_created_at)
Index("ix_agent_activities_run_sequence", AgentActivity.run_id, AgentActivity.sequence)
