"""
Shared investigation state.

This object flows through every node in the LangGraph pipeline.
Each agent reads what it needs from earlier stages and writes its
own findings into the state for later agents (and for the final
report) to consume.

Using a Pydantic model (rather than a plain TypedDict, which is
LangGraph's more common convention) gives us runtime validation --
useful here since the eval harness later depends on this data being
well-formed and consistently shaped across 18+ different runs.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    dependency = "Dependency Failure"
    test = "Test Failure"
    configuration = "Configuration Failure"
    database = "Database Failure"
    infrastructure = "Infrastructure Failure"
    build = "Build Failure"
    unknown = "Unknown"


class WorkflowRunInfo(BaseModel):
    """Populated by Agent 1 (Workflow Monitor)."""

    run_id: int
    repo_owner: str
    repo_name: str
    branch: str
    commit_sha: str
    commit_message: str
    workflow_name: str
    conclusion: str  # e.g. "failure"
    html_url: str
    created_at: datetime


class JobLog(BaseModel):
    """One failed job's raw log content, downloaded by Agent 1."""

    job_name: str
    job_id: int
    raw_log: str


class ClassificationResult(BaseModel):
    """Populated by Agent 2 (Failure Analyzer)."""

    category: FailureCategory
    confidence: float = Field(ge=0.0, le=1.0)
    relevant_log_excerpt: str
    root_cause_explanation: str


class RepoFinding(BaseModel):
    """Populated by Agent 3 (Repository Investigator)."""

    likely_files: list[str]
    supporting_evidence: str
    recent_relevant_commits: list[str] = Field(default_factory=list)


class FixRecommendation(BaseModel):
    """Populated by Agent 4 (Fix Recommendation Agent)."""

    suggested_fix: str
    confidence: float = Field(ge=0.0, le=1.0)


class InvestigationReport(BaseModel):
    """Populated by Agent 5 (Report Generator)."""

    markdown: str
    json_summary: dict


class IssueResult(BaseModel):
    """Populated by Agent 6 (GitHub Issue Creator)."""

    issue_number: int | None = None
    issue_url: str | None = None
    created: bool = False
    skipped_reason: str | None = None


class InvestigationState(BaseModel):
    """
    The full state object passed between LangGraph nodes.

    Each agent should only ever ADD a field, never mutate or remove
    earlier agents' findings -- this keeps the pipeline debuggable
    and keeps the eval harness able to inspect any intermediate
    stage's output, not just the final result.
    """

    run_info: WorkflowRunInfo
    job_logs: list[JobLog] = Field(default_factory=list)
    detected_tech_stack: str = "Unknown"

    classification: ClassificationResult | None = None
    repo_finding: RepoFinding | None = None
    fix_recommendation: FixRecommendation | None = None
    report: InvestigationReport | None = None
    issue_result: IssueResult | None = None

    errors: list[str] = Field(default_factory=list)
