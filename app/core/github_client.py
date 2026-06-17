"""
Thin wrapper over the GitHub REST API for the parts the investigator
needs: listing workflow runs, finding failed runs, downloading job
logs, and inspecting repo contents for tech-stack detection.

Uses PyGithub for the structured stuff (runs, jobs, metadata) and a
raw authenticated request for log downloads, since PyGithub doesn't
expose log content directly -- GitHub's log endpoint returns plain
text for a single job (what we use) or a zip for the whole run.

Takes repo_owner/repo_name as constructor args (not from global
config) so the same installation can investigate any repo without
code changes -- just pass a different owner/name per call.
"""

import requests
from github import Github

from app.core.config import settings


class GitHubClient:
    def __init__(self, repo_owner: str, repo_name: str) -> None:
        self.repo_owner = repo_owner
        self.repo_name = repo_name

        self._gh = Github(settings.GITHUB_TOKEN)
        self._repo = self._gh.get_repo(f"{repo_owner}/{repo_name}")
        self._headers = {
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }

    def get_latest_failed_run(self, branch: str | None = None):
        """
        Returns the most recent workflow run with conclusion == 'failure'
        for the repo (optionally filtered to a specific branch), or None
        if no failed runs exist.
        """
        kwargs = {"status": "failure"}
        if branch:
            kwargs["branch"] = branch

        runs = self._repo.get_workflow_runs(**kwargs)
        for run in runs:
            return run  # PaginatedList is already ordered newest-first
        return None

    def get_run_by_id(self, run_id: int):
        return self._repo.get_workflow_run(run_id)

    def get_failed_jobs(self, run) -> list:
        """Returns only the jobs within a run that did not succeed."""
        jobs = run.jobs()
        return [job for job in jobs if job.conclusion not in ("success", "skipped", None)]

    def download_job_log(self, job) -> str:
        """
        Downloads and returns the raw text log for a single job.

        job.logs_url() already performs the authenticated GitHub API
        call internally and returns the final, pre-signed cloud
        storage URL (Azure Blob, in practice) that the GitHub API
        redirects to. That URL has its own signature/token baked into
        its query string and must be fetched WITHOUT our GitHub auth
        header -- sending it causes a 401, since the storage service
        doesn't recognize (and actively rejects) a foreign bearer token.
        """
        url = job.logs_url()
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def get_commit_message(self, sha: str) -> str:
        commit = self._repo.get_commit(sha)
        return commit.commit.message

    def list_root_files(self, ref: str | None = None) -> list[str]:
        """
        Lists filenames at the repo root (optionally at a specific
        ref/branch). Used for lightweight tech-stack detection --
        e.g. presence of requirements.txt vs package.json vs go.mod.
        """
        kwargs = {"ref": ref} if ref else {}
        contents = self._repo.get_contents("", **kwargs)
        return [item.name for item in contents]

    def list_workflow_files(self, ref: str | None = None) -> list[str]:
        """
        Lists full relative paths of files inside .github/workflows/,
        if that directory exists. Used so Agent 3 (Repository
        Investigator) knows the ACTUAL workflow filename(s) rather
        than guessing (e.g. "ci.yml" vs "test.yml" vs "build.yml")
        when the root-level listing only shows ".github" as an
        opaque directory name.
        """
        try:
            kwargs = {"ref": ref} if ref else {}
            contents = self._repo.get_contents(".github/workflows", **kwargs)
            return [f".github/workflows/{item.name}" for item in contents]
        except Exception:
            return []

    def get_file_content(self, path: str, ref: str | None = None) -> str | None:
        """Returns the text content of a file at the given path, or None if not found."""
        try:
            kwargs = {"ref": ref} if ref else {}
            file_content = self._repo.get_contents(path, **kwargs)
            return file_content.decoded_content.decode("utf-8")
        except Exception:
            return None

    def create_issue(self, title: str, body: str) -> tuple[int, str]:
        """Creates a GitHub issue. Returns (issue_number, issue_url)."""
        issue = self._repo.create_issue(title=title, body=body)
        return issue.number, issue.html_url
