"""Centralised, environment-driven configuration for Edezee.

Every tunable lives here so operators can change behaviour without touching
pipeline code. Secrets are read from the environment only; nothing is ever
hardcoded or written back to disk.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for backend/.env by absolute path as well as .env in the working
# directory. Without this, running a script from the repository root (for
# example `make baseline`) silently found no configuration and reported the key
# as missing, even though backend/.env was correct. Later entries win, so a
# .env in the working directory still overrides the backend one.
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider ---------------------------------------------------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_site_url: str = "https://github.com/juwwad/edezee"
    openrouter_app_name: str = "Edezee"

    # --- Research provider ----------------------------------------------
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_search_depth: str = "advanced"
    tavily_max_results: int = Field(default=4, ge=1, le=10)

    # --- Pipeline behaviour ---------------------------------------------
    max_topic_attempts: int = Field(default=3, ge=1, le=6)
    llm_timeout_seconds: float = Field(default=90.0, gt=0)
    max_topics: int = Field(default=40, ge=1, le=200)
    inter_topic_delay_seconds: float = Field(default=0.0, ge=0)
    # Off by default. When on, the app serves deterministic sample content with
    # no API key so a reviewer can exercise the full flow (see services/demo.py).
    demo_mode: bool = False

    # --- Server ----------------------------------------------------------
    allowed_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_dir: str = "logs"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_configured(self) -> bool:
        # Demo mode is a deliberate substitute for a real key, so the health
        # check and the UI gate treat the app as ready when it is on.
        return bool(self.openrouter_api_key.strip()) or self.demo_mode

    @property
    def research_configured(self) -> bool:
        return bool(self.tavily_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
