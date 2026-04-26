from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class JobStep(StrEnum):
    INGEST = "ingest"
    FINANCE = "finance"
    SCRIPTER = "scripter"
    TTS = "tts"
    HERA_PLAN = "hera_plan"
    HERA_RENDER = "hera_render"
    COMPOSE = "compose"
    DONE = "done"


class GenerateResponse(BaseModel):
    job_id: str


class Scene(BaseModel):
    title: str = Field(min_length=1)
    narration: str = Field(min_length=1)

    @field_validator("narration")
    @classmethod
    def validate_narration_word_count(cls, value: str) -> str:
        # Scripter prompt targets 70–85 words; allow ±10 word slack so a
        # single off-count scene doesn't abort the entire pipeline.
        words = value.split()
        if not 60 <= len(words) <= 110:
            raise ValueError("Scene narration must be between 60 and 110 words.")
        return value


class Script(BaseModel):
    title: str = Field(min_length=1)
    scenes: list[Scene]

    @field_validator("scenes")
    @classmethod
    def validate_exactly_four_scenes(cls, value: list[Scene]) -> list[Scene]:
        if len(value) != 4:
            raise ValueError("Script must contain exactly 4 scenes.")
        return value


class SentenceTiming(BaseModel):
    scene_index: int = Field(ge=0)
    sentence: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class SlideChunk(BaseModel):
    text: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    char_count: int = Field(ge=1)


class JobStatus(BaseModel):
    status: JobState
    step: JobStep
    progress: int = Field(ge=0, le=100)
    error: str | None = None
    video_url: str | None = None
    hera_completed_clips: int = Field(default=0, ge=0)
    hera_total_clips: int = Field(default=0, ge=0)
    hera_attempt: int = Field(default=0, ge=0)
    hera_max_attempts: int = Field(default=0, ge=0)
