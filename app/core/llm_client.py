"""
Thin wrapper around the Groq chat completion API.

Agents that need LLM reasoning (classification, repo investigation,
fix recommendation, report writing) all go through this one helper
so the actual API call mechanics (auth, model name, JSON parsing,
error handling) live in exactly one place.
"""

import json

from groq import APIError, Groq

from app.core.config import settings

_client = Groq(api_key=settings.GROQ_API_KEY)

_JSON_SAFETY_INSTRUCTION = (
    "\n\nIMPORTANT: any log excerpt or quoted text you include in a JSON "
    "string field MUST be properly escaped (escape internal double quotes "
    "as \\\", escape newlines as \\n) and kept SHORT -- a single "
    "representative line or two, not a full multi-line traceback. Pasting "
    "raw unescaped log text into a JSON field breaks JSON syntax and will "
    "cause your entire response to be rejected."
)


def call_llm_json(
    system_prompt: str, user_prompt: str, max_tokens: int = 1024, max_retries: int = 2
) -> dict:
    """
    Calls the LLM with a system + user prompt, expecting a JSON object
    back. Uses Groq's JSON mode; retries with explicit feedback if the
    model produces invalid JSON (a real, observed failure mode: models
    sometimes paste raw multi-line log/traceback text into a JSON
    string field without escaping internal quotes/newlines, which
    breaks JSON syntax and causes Groq's strict json_object mode to
    reject the generation server-side before we even see it).

    Raises ValueError if all retries are exhausted -- callers should
    catch this and decide how to degrade gracefully (e.g. mark
    classification as "Unknown" with low confidence rather than
    crashing the whole pipeline).
    """
    augmented_system_prompt = system_prompt + _JSON_SAFETY_INSTRUCTION

    last_error_detail = None

    for attempt in range(max_retries + 1):
        messages = [
            {"role": "system", "content": augmented_system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if last_error_detail:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous response was rejected because: {last_error_detail}. "
                        "Try again, keeping all string field values short and properly "
                        "escaped. Respond ONLY with the corrected JSON object."
                    ),
                }
            )

        try:
            response = _client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except APIError as e:
            # Groq's server-side JSON validation rejected the
            # generation before returning it -- the error body
            # usually contains the malformed generation, which is
            # useful feedback for the retry.
            last_error_detail = str(e)[:400]
            if attempt < max_retries:
                continue
            raise ValueError(
                f"LLM failed to generate valid JSON after {max_retries + 1} attempts. "
                f"Last error: {last_error_detail}"
            ) from e

        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Some models occasionally wrap JSON in markdown fences even
            # when json_object mode is requested. Try to strip those.
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            try:
                return json.loads(cleaned.strip())
            except json.JSONDecodeError as e:
                last_error_detail = f"Invalid JSON syntax: {content[:300]}"
                if attempt < max_retries:
                    continue
                raise ValueError(
                    f"LLM did not return valid JSON after {max_retries + 1} attempts. "
                    f"Raw content: {content[:500]}"
                ) from e

    # Unreachable in practice (loop always returns or raises), but
    # keeps type checkers happy.
    raise ValueError(f"LLM failed to generate valid JSON. Last error: {last_error_detail}")


def call_llm_text(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> str:
    """Calls the LLM expecting free-form text back (e.g. for report prose)."""
    response = _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content
