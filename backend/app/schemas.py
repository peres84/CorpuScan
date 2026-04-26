from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceKind(StrEnum):
    PDF = "pdf"
    URL = "url"
    QUERY = "query"


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


class PdfTemplateId(StrEnum):
    GROWTH_COMPARISON = "growth_comparison"
    EARNINGS_COMPARISON = "earnings_comparison"


class OutputAspectRatio(StrEnum):
    DESKTOP = "16:9"
    MOBILE = "9:16"


class GenerateResponse(BaseModel):
    job_id: str


class BrandingPalette(BaseModel):
    background: str = Field(min_length=4)
    text: str = Field(min_length=4)
    secondary: str = Field(min_length=4)
    accent: str = Field(min_length=4)


class PdfDocumentMetadata(BaseModel):
    filename: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    period_label: str = Field(min_length=1)
    page_count: int = Field(ge=1)
    palette: BrandingPalette


class PipelineContext(BaseModel):
    source_kind: SourceKind
    output_aspect_ratio: OutputAspectRatio = OutputAspectRatio.DESKTOP
    template_id: PdfTemplateId | None = None
    pdf_documents: list[PdfDocumentMetadata] = Field(default_factory=list)
    branding: BrandingPalette | None = None
    company_name: str | None = None
    period_label: str | None = None


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
