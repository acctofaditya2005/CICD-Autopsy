"""
SQLAlchemy models for persisting investigation results.

One row per investigation run. Stores enough structured data to
query/filter later (category, confidence, repo) plus the full JSON
summary and markdown report as text blobs, so nothing from a past
investigation is lost even as the schema evolves.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)

    repo_owner = Column(String, nullable=False, index=True)
    repo_name = Column(String, nullable=False, index=True)
    branch = Column(String, nullable=True)
    run_id = Column(Integer, nullable=False, index=True)
    commit_sha = Column(String, nullable=False)

    detected_tech_stack = Column(String, nullable=True)
    category = Column(String, nullable=False, index=True)
    classification_confidence = Column(Float, nullable=False)
    root_cause_explanation = Column(Text, nullable=True)

    likely_files_json = Column(Text, nullable=True)  # JSON-encoded list[str]
    suggested_fix = Column(Text, nullable=True)
    fix_confidence = Column(Float, nullable=True)

    issue_created = Column(Integer, nullable=False, default=0)  # 0/1 bool
    issue_url = Column(String, nullable=True)

    report_markdown = Column(Text, nullable=True)
    report_json = Column(Text, nullable=True)  # full JSON summary, encoded

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
