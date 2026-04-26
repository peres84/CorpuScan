from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_DEFAULT_DEV_CORS_ORIGINS = ("http://localhost:5173", "http://localhost:8080")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = Field(default="")
    tavily_api_key: str = Field(default="")
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")
    hera_api_key: str = Field(default="")
    hera_base_url: str = Field(default="https://api.hera.video/v1")
    hera_render_timeout_seconds: int = Field(default=240, ge=30)
    hera_render_retry_attempts: int = Field(default=3, ge=1)
    hera_poll_interval_seconds: float = Field(default=3.0, gt=0)
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8080,https://corpuscan.vercel.app",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        configured = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        if "*" in configured:
            return ["*"]
        merged = list(dict.fromkeys([*configured, *_DEFAULT_DEV_CORS_ORIGINS]))
        return merged


# No lru_cache — settings must be fresh on each process start so .env changes are picked up
def get_settings() -> Settings:
    return Settings()
