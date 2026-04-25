from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


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


class SentenceTiming(BaseModel):
    scene_index: int = Field(ge=0)
    sentence: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class JobStatus(BaseModel):
    status: JobState
    step: JobStep
    progress: int = Field(ge=0, le=100)
    error: str | None = None
    video_url: str | None = None
