"""
Configuration for the CI/CD Failure Investigator.

Required environment variables:
  GITHUB_TOKEN        - Personal access token with repo + actions:read scope
  GROQ_API_KEY        - free tier available at console.groq.com, used for
                        the LLM-based classification/reasoning steps

Note: the target repo (owner/name) is NOT configured here. It's passed
as a parameter when starting an investigation, so this same installation
can be pointed at any repo without code changes.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- GitHub ---
    GITHUB_TOKEN: str

    # --- LLM (Groq) ---
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.3-70b-versatile"

    # --- Storage ---
    DATABASE_URL: str = "sqlite:///./investigator.db"

    # --- App ---
    APP_NAME: str = "cicd-autopsy"


settings = Settings()
