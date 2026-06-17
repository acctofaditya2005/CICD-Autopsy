"""
Persists a completed InvestigationState into the investigations table.
"""

import json

from sqlalchemy.orm import Session

from app.db.models import InvestigationRecord
from app.models.state import InvestigationState


def save_investigation(state: InvestigationState, db: Session) -> InvestigationRecord:
    classification = state.classification
    repo_finding = state.repo_finding
    fix = state.fix_recommendation
    issue = state.issue_result
    report = state.report

    record = InvestigationRecord(
        repo_owner=state.run_info.repo_owner,
        repo_name=state.run_info.repo_name,
        branch=state.run_info.branch,
        run_id=state.run_info.run_id,
        commit_sha=state.run_info.commit_sha,
        detected_tech_stack=state.detected_tech_stack,
        category=classification.category.value if classification else "Unknown",
        classification_confidence=classification.confidence if classification else 0.0,
        root_cause_explanation=classification.root_cause_explanation if classification else None,
        likely_files_json=json.dumps(repo_finding.likely_files) if repo_finding else None,
        suggested_fix=fix.suggested_fix if fix else None,
        fix_confidence=fix.confidence if fix else None,
        issue_created=1 if (issue and issue.created) else 0,
        issue_url=issue.issue_url if issue else None,
        report_markdown=report.markdown if report else None,
        report_json=json.dumps(report.json_summary) if report else None,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record
