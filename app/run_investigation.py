"""
CLI entrypoint: runs a full investigation against a real repo.

Usage:
  python -m app.run_investigation --owner acctofaditya2005 --repo Taskhub-api --branch break/dep-missing-jose
  python -m app.run_investigation --owner acctofaditya2005 --repo Taskhub-api --run-id 123456

By default, issue creation runs in dry-run mode (won't actually post
to GitHub). Pass --create-issue to actually create a real issue.
"""

import argparse
import json

from app.agents.workflow_monitor import run_workflow_monitor
from app.core.github_client import GitHubClient
from app.db.crud import save_investigation
from app.db.session import SessionLocal, init_db
from app.graph import build_graph
from app.models.state import InvestigationState


def run_investigation(
    repo_owner: str,
    repo_name: str,
    branch: str | None = None,
    run_id: int | None = None,
    dry_run_issue_creation: bool = True,
    persist: bool = True,
    include_commit_message_in_classification: bool = False,
) -> InvestigationState:
    """
    Runs the full 6-agent pipeline against a real repo and returns
    the final InvestigationState. If persist=True (default), also
    saves the result to the local database.

    include_commit_message_in_classification defaults to False so
    Agent 2 is scored on genuine log-reading, not on commit messages
    that may give away the answer (true of our own synthetic
    taskhub-api branches; real-world commits are rarely this
    self-describing anyway).
    """
    print(f"[Agent 1] Finding failed run for {repo_owner}/{repo_name}...")
    state = run_workflow_monitor(
        repo_owner=repo_owner, repo_name=repo_name, branch=branch, run_id=run_id
    )
    print(f"  Found run {state.run_info.run_id} on branch '{state.run_info.branch}'")
    print(f"  Detected tech stack: {state.detected_tech_stack}")
    print(f"  Collected {len(state.job_logs)} failed job log(s)")

    github_client = GitHubClient(repo_owner=repo_owner, repo_name=repo_name)
    graph = build_graph(
        github_client=github_client,
        dry_run_issue_creation=dry_run_issue_creation,
        include_commit_message_in_classification=include_commit_message_in_classification,
    )

    print("[Agents 2-6] Running classification, repo investigation, fix "
          "recommendation, report generation, issue creation...")
    result_dict = graph.invoke(state)
    final_state = InvestigationState(**result_dict)

    if persist:
        init_db()
        db = SessionLocal()
        try:
            save_investigation(final_state, db)
            print("  Saved investigation to local database.")
        finally:
            db.close()

    return final_state


def main():
    parser = argparse.ArgumentParser(description="Run a CI/CD failure investigation")
    parser.add_argument("--owner", required=True, help="Repo owner")
    parser.add_argument("--repo", required=True, help="Repo name")
    parser.add_argument("--branch", help="Branch to find the latest failed run on")
    parser.add_argument("--run-id", type=int, help="Specific run ID to investigate")
    parser.add_argument(
        "--create-issue", action="store_true", help="Actually create a GitHub issue (default: dry run)"
    )
    parser.add_argument(
        "--include-commit-message",
        action="store_true",
        help="Give the classifier the commit message (default: off, since our "
        "synthetic break/* commit messages give away the answer)",
    )
    args = parser.parse_args()

    if not args.branch and not args.run_id:
        parser.error("Either --branch or --run-id is required")

    final_state = run_investigation(
        repo_owner=args.owner,
        repo_name=args.repo,
        branch=args.branch,
        run_id=args.run_id,
        dry_run_issue_creation=not args.create_issue,
        include_commit_message_in_classification=args.include_commit_message,
    )

    print("\n" + "=" * 60)
    print(final_state.report.markdown)
    print("=" * 60)

    if final_state.issue_result:
        if final_state.issue_result.created:
            print(f"\nIssue created: {final_state.issue_result.issue_url}")
        else:
            print(f"\nIssue NOT created: {final_state.issue_result.skipped_reason}")

    if final_state.errors:
        print("\nWarnings/errors encountered during investigation:")
        for err in final_state.errors:
            print(f"  - {err}")

    print("\nFull JSON summary:")
    print(json.dumps(final_state.report.json_summary, indent=2))


if __name__ == "__main__":
    main()
