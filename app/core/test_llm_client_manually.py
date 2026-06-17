"""
Standalone sanity check for the Groq LLM client. Run locally with
your real .env in place.

Run with:  python -m app.core.test_llm_client_manually
"""

from app.core.llm_client import call_llm_json, call_llm_text


def main():
    print("=== Testing call_llm_text ===")
    text = call_llm_text(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say 'hello from groq' and nothing else.",
        max_tokens=50,
    )
    print(f"Response: {text}")

    print("\n=== Testing call_llm_json ===")
    result = call_llm_json(
        system_prompt=(
            "You are a CI/CD failure classifier. Given a log excerpt, "
            "respond ONLY with a JSON object with this exact shape: "
            '{"category": "...", "confidence": 0.0-1.0, "explanation": "..."}'
        ),
        user_prompt=(
            "Log excerpt:\n"
            "ModuleNotFoundError: No module named 'jose'\n\n"
            "Classify this failure. Category must be one of: "
            "Dependency Failure, Test Failure, Configuration Failure, "
            "Database Failure, Infrastructure Failure, Build Failure."
        ),
        max_tokens=300,
    )
    print(f"Parsed JSON: {result}")
    print(f"Category: {result.get('category')}")
    print(f"Confidence: {result.get('confidence')}")


if __name__ == "__main__":
    main()
