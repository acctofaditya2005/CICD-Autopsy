"""
Agent 4: Fix Recommendation Agent

Given the classification (Agent 2) and the repo finding with real
file content (Agent 3), generates a concrete suggested fix and a
confidence score.

Confidence here is meant to reflect how directly the evidence
supports the suggestion -- e.g. high if Agent 3 found and quoted the
exact problematic line, low if Agent 3 couldn't confirm any file at
all and this is mostly inferred from the log alone.
"""

from app.core.llm_client import call_llm_json
from app.models.state import FixRecommendation, InvestigationState

_SYSTEM_PROMPT = """You are a senior engineer reviewing a CI/CD failure \
investigation. You have the failure classification, root cause \
explanation, and the specific file(s) believed to be responsible \
(with supporting evidence). Write a concrete, actionable fix.

Be specific: name the exact file, the exact line/value/import that's \
wrong, and what it should be instead. Do not give generic advice like \
"check your configuration" -- give the actual fix.

Respond ONLY with a JSON object:
{
  "suggested_fix": "<specific, actionable fix description>",
  "confidence": <float 0.0-1.0, reflecting how directly the evidence \
supports this fix -- lower if the responsible file couldn't be \
confirmed>
}"""


def run_fix_recommender(state: InvestigationState) -> InvestigationState:
    """
    Entry point for Agent 4. Reads state.classification and
    state.repo_finding, writes state.fix_recommendation.
    """
    if state.classification is None:
        state.errors.append("Fix Recommender: no classification available, skipping")
        return state

    repo_finding = state.repo_finding
    likely_files = repo_finding.likely_files if repo_finding else []
    supporting_evidence = repo_finding.supporting_evidence if repo_finding else "None available"

    user_prompt = f"""Failure category: {state.classification.category.value}
Root cause explanation: {state.classification.root_cause_explanation}
Relevant log excerpt: {state.classification.relevant_log_excerpt}

Likely responsible file(s): {likely_files}
Supporting evidence: {supporting_evidence}"""

    try:
        result = call_llm_json(_SYSTEM_PROMPT, user_prompt, max_tokens=500)
        state.fix_recommendation = FixRecommendation(
            suggested_fix=result.get("suggested_fix", ""),
            confidence=float(result.get("confidence", 0.0)),
        )
    except Exception as e:
        state.errors.append(f"Fix Recommender: LLM call failed: {e}")
        state.fix_recommendation = FixRecommendation(
            suggested_fix=f"Could not generate a fix recommendation due to an error: {e}",
            confidence=0.0,
        )

    return state
