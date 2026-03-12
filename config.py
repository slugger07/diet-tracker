"""
Centralized configuration for NutriLog India.
All settings loaded from environment variables with safe defaults.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class LLMProvider(str, Enum):
    GROQ = "groq"
    OLLAMA = "ollama"


class SearchProvider(str, Enum):
    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"


class Settings(BaseSettings):
    """Application settings – reads from .env automatically."""

    # --- LLM ---
    llm_provider: LLMProvider = Field(default=LLMProvider.GROQ)
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.1-8b-instant")
    ollama_model: str = Field(default="llama3.1")
    ollama_base_url: str = Field(default="http://localhost:11434")

    # --- Search ---
    search_provider: SearchProvider = Field(default=SearchProvider.DUCKDUCKGO)
    tavily_api_key: str = Field(default="")

    # --- Database ---
    database_url: str = Field(default="sqlite:///nutrilog.db")

    # --- App ---
    log_level: str = Field(default="INFO")
    default_user: str = Field(default="default")

    # --- Nutrition cache TTL (days) ---
    cache_ttl_days: int = Field(default=30)

    # --- SSL ---
    ssl_cert_file: str = Field(default="", description="Path to custom CA bundle for corporate proxies")

    # --- Paths ---
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def db_path(self) -> Path:
        """Resolve the SQLite file path from the database_url."""
        url = self.database_url
        if url.startswith("sqlite:///"):
            relative = url.replace("sqlite:///", "")
            return self.base_dir / relative
        return Path(url)

    @property
    def ca_bundle_path(self) -> str | None:
        """Return the CA bundle path if a custom one is configured or auto-detected."""
        # 1. Explicit env var
        if self.ssl_cert_file:
            return self.ssl_cert_file
        # 2. Auto-detect combined bundle in project root
        combined = self.base_dir / "cacert_combined.pem"
        if combined.exists():
            return str(combined)
        # 3. Check SSL_CERT_FILE env var
        env_cert = os.environ.get("SSL_CERT_FILE")
        if env_cert and Path(env_cert).exists():
            return env_cert
        return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor – cached after first call."""
    return Settings()

