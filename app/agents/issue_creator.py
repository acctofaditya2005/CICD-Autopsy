"""
Agent 6: GitHub Issue Creator

Takes the assembled report from Agent 5 and opens a real GitHub
issue on the target repo. Includes a safety valve: if classification
confidence is very low (meaning the earlier agents weren't able to
figure out much), skip issue creation rather than spam the repo with
a low-value issue, and record why it was skipped.
"""

from app.core.github_client import GitHubClient
from app.models.state import InvestigationState, IssueResult

_MIN_CONFIDENCE_TO_CREATE_ISSUE = 0.3


def run_issue_creator(
    state: InvestigationState,
    github_client: GitHubClient,
    dry_run: bool = False,
) -> InvestigationState:
    """
    Entry point for Agent 6. Reads state.report and
    state.classification, writes state.issue_result.

    If dry_run=True, builds the issue title/body but does not
    actually call the GitHub API -- useful for testing the full
    pipeline without creating real issues on every test run.
    """
    if state.report is None:
        state.issue_result = IssueResult(
            created=False, skipped_reason="No report available to create an issue from"
        )
        return state

    confidence = state.classification.confidence if state.classification else 0.0
    if confidence < _MIN_CONFIDENCE_TO_CREATE_ISSUE:
        state.issue_result = IssueResult(
            created=False,
            skipped_reason=(
                f"Classification confidence ({confidence:.2f}) below threshold "
                f"({_MIN_CONFIDENCE_TO_CREATE_ISSUE}); skipping issue creation "
                "to avoid low-value noise."
            ),
        )
        return state

    category = state.classification.category.value if state.classification else "Unknown"
    title = f"[CI Failure] {category}: {state.run_info.commit_message.splitlines()[0][:80]}"

    if dry_run:
        state.issue_result = IssueResult(
            created=False,
            skipped_reason=f"dry_run=True; would have created issue titled: {title}",
        )
        return state

    try:
        issue_number, issue_url = github_client.create_issue(
            title=title, body=state.report.markdown
        )
        state.issue_result = IssueResult(
            issue_number=issue_number, issue_url=issue_url, created=True
        )
    except Exception as e:
        state.errors.append(f"Issue Creator: failed to create issue: {e}")
        state.issue_result = IssueResult(created=False, skipped_reason=f"API error: {e}")

    return state
