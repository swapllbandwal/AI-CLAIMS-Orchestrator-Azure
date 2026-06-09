"""Application settings loaded from .env (pydantic-settings)."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in both the backend folder and the project root one level up,
# so it works whether the file lives next to main.py or at the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    # Azure Computer Vision
    azure_cv_endpoint: str = Field(..., description="Azure Computer Vision endpoint URL")
    azure_cv_key: str = Field(..., description="Azure Computer Vision API key")

    # Microsoft Foundry / Claude
    foundry_endpoint: str = Field(..., description="Microsoft Foundry base URL (Anthropic-compatible)")
    foundry_api_key: str = Field(..., description="Microsoft Foundry API key")
    foundry_model: str = Field("claude-sonnet-4-6", description="Model deployment name")

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug_mode: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    # RAG
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
