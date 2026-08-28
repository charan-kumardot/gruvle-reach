"""
Central settings. Every field has a safe default so the application boots with
just a database configured — optional integrations (AI beyond Ollama, search,
email, social) are read at call time by their own provider factories and
degrade to a disabled/mock state rather than raising here.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root_env_file() -> str:
    """Look for a repo-root `.env` a few levels up from this file, for local
    dev convenience. In a container (Docker/Render/Vercel) there is no such
    file — env vars are injected by the platform instead — so this must
    degrade to "no dotenv" rather than raising if the directory tree is
    shallower than expected (e.g. /app/app/core/config.py inside the image)."""
    here = Path(__file__).resolve()
    for candidate in here.parents:
        env_path = candidate / ".env"
        if env_path.is_file():
            return str(env_path)
    return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_find_repo_root_env_file(), extra="ignore")

    app_env: str = "development"
    secret_key: str = "insecure-dev-key-change-me"
    encryption_key: str = ""  # Fernet key; if blank, credential encryption is disabled (dev only)

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/gruvle_reach"
    database_url_direct: str = ""

    redis_url: str = "redis://localhost:6379/0"

    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    # AI provider
    ai_provider: Literal["ollama", "groq", "openai_compatible"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = ""

    # Search provider
    search_provider: Literal["searxng", "rss", "manual"] = "searxng"
    searxng_base_url: str = "http://localhost:8888"

    # Email provider
    email_provider: Literal["resend", "smtp", "disabled"] = "disabled"
    resend_api_key: str = ""
    resend_from_email: str = "Gruvle Reach <onboarding@resend.dev>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # Social (all optional — presence of both id+secret is what "configured" means)
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    producthunt_client_id: str = ""
    producthunt_client_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""

    slack_webhook_url: str = ""

    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def database_url_for_migrations(self) -> str:
        return self.database_url_direct or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
