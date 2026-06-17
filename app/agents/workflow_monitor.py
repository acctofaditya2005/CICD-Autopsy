"""
Agent 1: Workflow Monitor

Connects to GitHub, finds a failed workflow run (either the latest
on a given branch, or a specific run_id), downloads logs for every
failed job, and populates the initial InvestigationState.

This agent does no LLM reasoning -- it's pure data collection. Kept
deliberately "dumb" so failures here are about API/auth issues, not
prompt issues, which makes debugging much easier.
"""

from app.core.github_client import GitHubClient
from app.core.tech_stack import detect_tech_stack
from app.models.state import InvestigationState, JobLog, WorkflowRunInfo


def run_workflow_monitor(
    repo_owner: str,
    repo_name: str,
    branch: str | None = None,
    run_id: int | None = None,
) -> InvestigationState:
    """
    Entry point for Agent 1. Either branch or run_id should be given:
      - branch: finds the most recent failed run on that branch
      - run_id: investigates that specific run directly

    Raises ValueError if no failed run can be found.
    """
    client = GitHubClient(repo_owner=repo_owner, repo_name=repo_name)

    if run_id is not None:
        run = client.get_run_by_id(run_id)
    else:
        run = client.get_latest_failed_run(branch=branch)

    if run is None:
        raise ValueError(
            f"No failed workflow run found for {repo_owner}/{repo_name}"
            + (f" on branch '{branch}'" if branch else "")
        )

    commit_message = client.get_commit_message(run.head_sha)

    run_info = WorkflowRunInfo(
        run_id=run.id,
        repo_owner=repo_owner,
        repo_name=repo_name,
        branch=run.head_branch,
        commit_sha=run.head_sha,
        commit_message=commit_message,
        workflow_name=run.name,
        conclusion=run.conclusion,
        html_url=run.html_url,
        created_at=run.created_at,
    )

    failed_jobs = client.get_failed_jobs(run)
    job_logs = []
    for job in failed_jobs:
        try:
            raw_log = client.download_job_log(job)
        except Exception as e:
            raw_log = f"[Failed to download log for job '{job.name}': {e}]"
        job_logs.append(JobLog(job_name=job.name, job_id=job.id, raw_log=raw_log))

    state = InvestigationState(run_info=run_info, job_logs=job_logs)

    # Stash tech stack detection in errors-adjacent metadata for now;
    # downstream agents read it via the helper below rather than a
    # dedicated state field, keeping this agent's job narrowly scoped
    # to "find the run and get the logs."
    try:
        root_files = client.list_root_files(ref=run.head_sha)
        state.detected_tech_stack = detect_tech_stack(root_files)
    except Exception as e:
        state.errors.append(f"Tech stack detection failed: {e}")

    return state
