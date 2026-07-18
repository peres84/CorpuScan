from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    TXT = "txt"
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"
    DOCX = "docx"
    XML = "xml"
    MD = "md"
    UNKNOWN = "unknown"


class ContentChunk(BaseModel):
    text: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)


class ParsedDocument(BaseModel):
    doc_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    doc_type: DocumentType
    content_chunks: list[ContentChunk] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    page_count: int = Field(ge=0, default=0)
