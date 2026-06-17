"""
Agent 2: Failure Analyzer

Takes the raw logs collected by Agent 1, extracts the most relevant
excerpt (the actual error, not the full noisy log), classifies the
failure into one of six categories, and produces a root-cause
explanation -- via a single LLM call.

Log extraction strategy: CI logs frequently have noise AFTER the
real error (post-job cleanup, container teardown, deprecation
warnings, etc.) -- confirmed directly against a real GitHub Actions
log, where a ModuleNotFoundError sat ~8,400 characters from the end
but trailing noise pushed it outside a naive "last 6000 chars"
window entirely. Blindly truncating from the end is therefore unsafe:
it can silently exclude the actual error and leave the model
reasoning over irrelevant trailing text while still sounding
confident.

Instead, we search for known error-signal markers (tracebacks,
"Error", GitHub Actions' own "##[error]" annotation, etc.) and build
a window AROUND the first such marker, not just around the end of
the log. Falls back to a last-N-chars window only if no markers are
found at all.
"""

import re

from app.core.llm_client import call_llm_json
from app.models.state import ClassificationResult, FailureCategory, InvestigationState

_MAX_LOG_CHARS_PER_JOB = 6000
_CONTEXT_BEFORE_MARKER = 1500
_MAX_WINDOW_AFTER_MARKER = 4000  # generous ceiling, used only if no end-anchor is found

# Ordered roughly by specificity/reliability as a real error signal.
# GitHub Actions' own "##[error]" annotation is the most reliable,
# since GitHub itself inserts it specifically to flag the failure
# line, not something we're inferring from log content.
_ERROR_MARKERS = [
    "##[error]",
    "Traceback (most recent call last)",
    "FAILED",
    "Error:",
    "ERROR",
    "error:",
]

# Matches a Python exception's final line, e.g.
# "ModuleNotFoundError: No module named 'jose'" or
# "pydantic_core._pydantic_core.ValidationError: 1 validation error..."
# This is deliberately broader than just "Error:" -- it requires a
# capitalized identifier immediately before the colon, which is what
# distinguishes an actual exception class name from incidental text
# that happens to contain the word "error".
_EXCEPTION_LINE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception):.*$", re.MULTILINE)


def _extract_relevant_excerpt(raw_log: str) -> str:
    """
    Finds the most likely location of the actual error in a raw log
    and returns a window spanning from where the traceback/error
    starts to where the actual exception is stated -- NOT a fixed
    character budget after the start marker.

    This matters because tracebacks vary a lot in length: a fixed
    "1500 chars after the marker" window was confirmed (against a
    real GitHub Actions log) to cut off mid-traceback for a deeply
    nested call stack (alembic -> script.run_env -> load_python_file
    -> ... -> the actual Pydantic ValidationError), silently hiding
    the real error from the classifier despite the traceback START
    marker being found correctly.

    Falls back to the last _MAX_LOG_CHARS_PER_JOB characters if no
    recognizable error marker is found anywhere in the log.
    """
    earliest_marker_pos = None
    for marker in _ERROR_MARKERS:
        pos = raw_log.find(marker)
        if pos != -1 and (earliest_marker_pos is None or pos < earliest_marker_pos):
            earliest_marker_pos = pos

    if earliest_marker_pos is None:
        return raw_log[-_MAX_LOG_CHARS_PER_JOB:]

    start = max(0, earliest_marker_pos - _CONTEXT_BEFORE_MARKER)

    # Look for the actual exception line AFTER the start marker,
    # within a generous search ceiling, rather than assuming a fixed
    # distance. This is what lets the window correctly grow to
    # accommodate deep call stacks.
    search_region_end = min(len(raw_log), earliest_marker_pos + _MAX_WINDOW_AFTER_MARKER)
    search_region = raw_log[earliest_marker_pos:search_region_end]

    exception_match = _EXCEPTION_LINE_PATTERN.search(search_region)
    if exception_match:
        # Extend the window a bit past the exception line itself, in
        # case there's a one-line continuation (rare but possible).
        end = earliest_marker_pos + exception_match.end() + 200
        end = min(end, len(raw_log))
    else:
        # No clear exception line found within the search ceiling --
        # use the full generous window rather than guess further.
        end = search_region_end

    return raw_log[start:end]

_SYSTEM_PROMPT = """You are an expert CI/CD failure investigator. You will be \
given raw log output from a failed GitHub Actions job, along with the \
detected tech stack and the commit message that triggered the run.

Classify the failure into EXACTLY ONE of these six categories:
- Dependency Failure: package install/resolution failures, missing or \
incompatible packages, ModuleNotFoundError, ImportError caused by a \
package not being installed.
- Test Failure: a test assertion fails due to application logic being \
wrong (not due to environment/config/infra issues).
- Configuration Failure: missing or malformed environment variables, \
settings validation errors, wrong config values (e.g. wrong algorithm \
name, wrong port).
- Database Failure: migration failures, schema/constraint violations, \
malformed database connection strings, SQL errors.
- Infrastructure Failure: Docker build failures, container \
orchestration issues, networking/timing issues between services.
- Build Failure: code-level errors that prevent the application from \
even being imported/compiled -- syntax errors, circular imports, \
referencing undefined names, importing nonexistent symbols from a \
package that IS installed correctly (distinguish this from Dependency \
Failure, where the package itself is missing/misconfigured).

Respond ONLY with a JSON object in this exact shape, no other text:
{
  "category": "<one of the six category names exactly as written above>",
  "confidence": <float between 0.0 and 1.0>,
  "relevant_log_excerpt": "<ONE SINGLE LINE from the log that shows the \
actual error -- e.g. just the line containing 'Error:' or 'Traceback' or \
similar. Do NOT include multiple lines, do NOT include a full traceback. \
One line only, under 200 characters, with any double quotes inside it \
escaped as \\\". This is a hard requirement -- multi-line excerpts break \
JSON parsing.>",
  "root_cause_explanation": "<2-4 sentences explaining what actually went \
wrong and why, in your own words -- prose only, no code or log snippets \
that would need escaping>"
}"""


def _build_user_prompt(state: InvestigationState, include_commit_message: bool = False) -> str:
    """
    include_commit_message defaults to False on purpose.

    Our taskhub-api eval branches have commit messages that openly
    state the bug (e.g. "break: remove python-jose dependency") --
    useful for human readers of FAILURE_MATRIX.md, but it makes the
    commit message an answer key in disguise during evaluation. A
    classifier that "succeeds" by reading the commit message isn't
    actually demonstrating log-reading ability, which is the whole
    point of this agent.

    Real-world commit messages are rarely this self-describing, so
    excluding it by default also more honestly reflects production
    conditions. Set include_commit_message=True only when you
    deliberately want to test commit-message-assisted classification
    as a separate, explicitly-labeled scenario.
    """
    log_sections = []
    for job_log in state.job_logs:
        excerpt = _extract_relevant_excerpt(job_log.raw_log)
        log_sections.append(f"--- Job: {job_log.job_name} ---\n{excerpt}")

    logs_text = "\n\n".join(log_sections) if log_sections else "(no logs available)"

    commit_line = f"Commit message: {state.run_info.commit_message}\n" if include_commit_message else ""
    branch_line = f"Branch: {state.run_info.branch}\n" if include_commit_message else ""

    return f"""Tech stack: {state.detected_tech_stack}
{commit_line}{branch_line}
{logs_text}"""


def run_failure_analyzer(
    state: InvestigationState, include_commit_message: bool = False
) -> InvestigationState:
    """
    Entry point for Agent 2. Reads state.job_logs (populated by
    Agent 1) and writes state.classification.

    include_commit_message: see _build_user_prompt docstring. Default
    False so classification is scored on genuine log-reading ability,
    not on commit messages that give away the answer.
    """
    if not state.job_logs:
        state.classification = ClassificationResult(
            category=FailureCategory.unknown,
            confidence=0.0,
            relevant_log_excerpt="",
            root_cause_explanation="No job logs were available to analyze.",
        )
        state.errors.append("Failure Analyzer: no job logs to analyze")
        return state

    user_prompt = _build_user_prompt(state, include_commit_message=include_commit_message)

    try:
        result = call_llm_json(_SYSTEM_PROMPT, user_prompt, max_tokens=600)

        category_raw = result.get("category", "Unknown")
        try:
            category = FailureCategory(category_raw)
        except ValueError:
            category = FailureCategory.unknown
            state.errors.append(
                f"Failure Analyzer: LLM returned unrecognized category '{category_raw}'"
            )

        state.classification = ClassificationResult(
            category=category,
            confidence=float(result.get("confidence", 0.0)),
            relevant_log_excerpt=result.get("relevant_log_excerpt", ""),
            root_cause_explanation=result.get("root_cause_explanation", ""),
        )
    except Exception as e:
        state.errors.append(f"Failure Analyzer: LLM call failed: {e}")
        state.classification = ClassificationResult(
            category=FailureCategory.unknown,
            confidence=0.0,
            relevant_log_excerpt="",
            root_cause_explanation=f"Classification failed due to an error: {e}",
        )

    return state
