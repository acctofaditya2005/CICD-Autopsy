"""
Standalone sanity check for the GitHub client. Run this locally
(with your real .env in place) to confirm:
  1. Auth works
  2. We can find the most recent failed run
  3. We can pull its failed jobs
  4. We can download a real log

Run with:
  python -m app.core.test_github_client_manually <owner> <repo> [branch]

Example:
  python -m app.core.test_github_client_manually acctofaditya2005 Taskhub-api break/dep-missing-jose
"""

import sys

from app.core.github_client import GitHubClient


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m app.core.test_github_client_manually <owner> <repo> [branch]")
        sys.exit(1)

    repo_owner = sys.argv[1]
    repo_name = sys.argv[2]
    branch = sys.argv[3] if len(sys.argv) > 3 else "break/dep-missing-jose"

    client = GitHubClient(repo_owner=repo_owner, repo_name=repo_name)

    print(f"Looking for the most recent failed run on {branch}...")
    run = client.get_latest_failed_run(branch=branch)

    if run is None:
        print("No failed run found on that branch. Is the branch name correct?")
        return

    print(f"Found run: id={run.id}, conclusion={run.conclusion}, branch={run.head_branch}")
    print(f"Commit SHA: {run.head_sha}")
    print(f"HTML URL: {run.html_url}")

    commit_message = client.get_commit_message(run.head_sha)
    print(f"Commit message: {commit_message[:80]}...")

    failed_jobs = client.get_failed_jobs(run)
    print(f"\nFound {len(failed_jobs)} failed job(s):")
    for job in failed_jobs:
        print(f"  - {job.name} (conclusion={job.conclusion})")

    if failed_jobs:
        print("\nDownloading log for first failed job...")
        log_text = client.download_job_log(failed_jobs[0])
        print(f"Log length: {len(log_text)} characters")
        print("--- Last 500 characters of log ---")
        print(log_text[-500:])


if __name__ == "__main__":
    main()
