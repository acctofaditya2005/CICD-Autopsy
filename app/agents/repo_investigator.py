"""
Agent 3: Repository Investigator

Given the classification from Agent 2, looks at the actual repo
content (root file listing, and -- for likely candidate files
suggested by the LLM's first pass -- their content) to pin down
which specific file(s) are responsible, and gathers any supporting
evidence (e.g. confirming a string actually appears in the file).

Two-pass approach:
  1. Ask the LLM, given the classification + log + repo file listing,
     to GUESS which files are most likely responsible.
  2. Fetch those files' real content from GitHub and ask the LLM to
     confirm/refine its guess using the actual file contents.

This catches cases where the first guess is plausible-sounding but
wrong (e.g. guessing app/models/task.py for a bug that's actually in
app/schemas/task.py) by grounding the second pass in real file text
rather than the LLM's assumptions about typical project layouts.
"""

from app.core.github_client import GitHubClient
from app.core.llm_client import call_llm_json
from app.models.state import InvestigationState, RepoFinding

_GUESS_SYSTEM_PROMPT = """You are investigating a CI/CD failure in a code \
repository. Based on the failure category, root cause explanation, and log \
excerpt, suggest which file(s) in the repository are MOST LIKELY responsible.

You will be given a partial list of files/directories in the repo. Use \
your knowledge of common project conventions for the detected tech stack \
to guess full relative paths (e.g. "app/core/config.py") even though you \
can only see top-level names.

IMPORTANT: not every failure's root cause lives in application code. \
Specifically:
- If the failure category is Configuration Failure AND the root cause \
involves an environment variable being missing, malformed, or having the \
wrong value (rather than application code reading it incorrectly), the \
CI workflow file itself (e.g. ".github/workflows/ci.yml" or similar) is \
often the actual culprit -- that's commonly where env vars are SET for \
CI, as opposed to application config files, which only READ them. \
Consider both possibilities and pick based on what the log/root cause \
actually indicates: did the app fail to even read a value that should \
exist (suggests the CI workflow never set it), or did the app receive a \
value but mishandle it (suggests application code is the culprit)?
- If the failure category is Database Failure and involves a malformed \
connection string or credentials (as opposed to a bad migration file), \
the CI workflow's env block is also a likely candidate, not just \
application config or migration files.

Respond ONLY with a JSON object:
{
  "candidate_files": ["<most likely file path>", "<second most likely>", ...],
  "reasoning": "<brief explanation of why these files are likely candidates>"
}
List at most 3 candidates, most likely first."""

_CONFIRM_SYSTEM_PROMPT = """You previously guessed which file(s) are \
responsible for a CI/CD failure. You are now given the ACTUAL CONTENT of \
those files. Confirm or correct your guess based on what you actually see.

Respond ONLY with a JSON object:
{
  "likely_files": ["<file path>", ...],
  "supporting_evidence": "<quote or reference the specific part of the file \
content that confirms this is the responsible file, or explain why none of \
the fetched files actually match if that's the case>"
}"""


def run_repo_investigator(
    state: InvestigationState, github_client: GitHubClient
) -> InvestigationState:
    """
    Entry point for Agent 3. Reads state.classification (from Agent 2)
    and writes state.repo_finding.
    """
    if state.classification is None:
        state.errors.append("Repo Investigator: no classification available, skipping")
        return state

    try:
        root_files = github_client.list_root_files(ref=state.run_info.commit_sha)
    except Exception as e:
        state.errors.append(f"Repo Investigator: failed to list root files: {e}")
        root_files = []

    try:
        workflow_files = github_client.list_workflow_files(ref=state.run_info.commit_sha)
    except Exception as e:
        state.errors.append(f"Repo Investigator: failed to list workflow files: {e}")
        workflow_files = []

    workflow_files_line = (
        f"\nActual CI workflow file path(s): {workflow_files}" if workflow_files else ""
    )

    guess_prompt = f"""Tech stack: {state.detected_tech_stack}
Failure category: {state.classification.category.value}
Root cause explanation: {state.classification.root_cause_explanation}
Relevant log excerpt: {state.classification.relevant_log_excerpt}

Top-level files/directories in the repo: {root_files}{workflow_files_line}"""

    try:
        guess_result = call_llm_json(_GUESS_SYSTEM_PROMPT, guess_prompt, max_tokens=400)
        candidate_files = guess_result.get("candidate_files", [])
    except Exception as e:
        state.errors.append(f"Repo Investigator: candidate-guess LLM call failed: {e}")
        candidate_files = []

    # Fetch real content for each candidate so the confirmation pass
    # is grounded in actual file text, not just plausible-sounding guesses.
    fetched_contents = {}
    for path in candidate_files[:3]:
        content = github_client.get_file_content(path, ref=state.run_info.commit_sha)
        if content is not None:
            fetched_contents[path] = content[:3000]  # bound size per file

    if not fetched_contents:
        # Nothing we guessed actually exists at that path -- report the
        # raw guesses with low confidence rather than silently failing.
        state.repo_finding = RepoFinding(
            likely_files=candidate_files,
            supporting_evidence=(
                "Could not fetch content for any candidate file "
                "(guessed paths may not exist or be incorrect)."
            ),
        )
        return state

    files_block = "\n\n".join(
        f"--- {path} ---\n{content}" for path, content in fetched_contents.items()
    )
    confirm_prompt = f"""Failure category: {state.classification.category.value}
Root cause explanation: {state.classification.root_cause_explanation}

Candidate file contents:
{files_block}"""

    try:
        confirm_result = call_llm_json(_CONFIRM_SYSTEM_PROMPT, confirm_prompt, max_tokens=500)
        state.repo_finding = RepoFinding(
            likely_files=confirm_result.get("likely_files", candidate_files),
            supporting_evidence=confirm_result.get("supporting_evidence", ""),
        )
    except Exception as e:
        state.errors.append(f"Repo Investigator: confirmation LLM call failed: {e}")
        state.repo_finding = RepoFinding(
            likely_files=candidate_files,
            supporting_evidence=f"Confirmation step failed: {e}",
        )

    return state
