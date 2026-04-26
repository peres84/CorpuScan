from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = Field(default="")
    tavily_api_key: str = Field(default="")
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")
    hera_api_key: str = Field(default="")
    hera_base_url: str = Field(default="https://api.hera.video/v1")
    cors_origins: str = Field(
        default="http://localhost:5173,https://corpuscan.vercel.app",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


# No lru_cache — settings must be fresh on each process start so .env changes are picked up
def get_settings() -> Settings:
    return Settings()
