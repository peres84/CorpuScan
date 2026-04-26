from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.ingest import (
    DEFAULT_BRANDING,
    build_comparison_source_text,
    detect_brand_palette,
    ensure_accessible_palette,
)
from app.main import _validate_generate_request
from app.schemas import BrandingPalette, OutputAspectRatio, PdfDocumentMetadata, PdfTemplateId


def test_validate_generate_request_rejects_mixed_sources() -> None:
    with pytest.raises(HTTPException, match="Provide exactly one source"):
        _validate_generate_request(
            files=[object()],  # type: ignore[list-item]
            url="https://example.com/report",
            query=None,
            template_id=PdfTemplateId.GROWTH_COMPARISON,
            output_aspect_ratio=OutputAspectRatio.DESKTOP,
        )


def test_validate_generate_request_requires_pdf_metadata() -> None:
    with pytest.raises(HTTPException, match="template_id"):
        _validate_generate_request(
            files=[object()],  # type: ignore[list-item]
            url=None,
            query=None,
            template_id=None,
            output_aspect_ratio=OutputAspectRatio.DESKTOP,
        )

    with pytest.raises(HTTPException, match="output_aspect_ratio"):
        _validate_generate_request(
            files=[object()],  # type: ignore[list-item]
            url=None,
            query=None,
            template_id=PdfTemplateId.GROWTH_COMPARISON,
            output_aspect_ratio=None,
        )


def test_validate_generate_request_rejects_more_than_four_pdfs() -> None:
    with pytest.raises(HTTPException, match="between 1 and 4 PDFs"):
        _validate_generate_request(
            files=[object(), object(), object(), object(), object()],  # type: ignore[list-item]
            url=None,
            query=None,
            template_id=PdfTemplateId.GROWTH_COMPARISON,
            output_aspect_ratio=OutputAspectRatio.DESKTOP,
        )


def test_build_comparison_source_text_keeps_document_boundaries() -> None:
    document = PdfDocumentMetadata(
        filename="apple-q2.pdf",
        company_name="Apple",
        period_label="Q2 2025",
        page_count=12,
        palette=DEFAULT_BRANDING,
    )
    combined = build_comparison_source_text([document], ["Revenue rose year over year."])
    assert "=== DOCUMENT 1 ===" in combined
    assert "Company: Apple" in combined
    assert "Reporting period: Q2 2025" in combined


def test_detect_brand_palette_uses_known_company_mapping() -> None:
    palette = detect_brand_palette("Tesla")
    assert palette.accent == "#E82127"


def test_ensure_accessible_palette_falls_back_when_contrast_is_weak() -> None:
    inaccessible = BrandingPalette(
        background="#FFFFFF",
        text="#FFFFFE",
        secondary="#FDFDFD",
        accent="#FFFFFF",
    )
    corrected = ensure_accessible_palette(inaccessible)
    assert corrected.text == "#111827"
    assert corrected.secondary == "#374151"
    assert corrected.accent == "#06B6D4"
