from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.structured import extract_unstructured


def _document(doc_type: DocumentType) -> ParsedDocument:
    return ParsedDocument(
        doc_id="document-1",
        filename="planning.pdf",
        doc_type=doc_type,
        content_chunks=[
            ContentChunk(
                text="Payments over €10,000 require two signatures for fiscal year 2025.",
                source_ref="planning.pdf:page:1",
                chunk_index=0,
            )
        ],
    )


class MockRouter:
    async def generate(self, **kwargs: object) -> str:
        return """[
            {
                "field": "payment_threshold",
                "value": "€10,000",
                "context": "Payments over this amount require two signatures"
            }
        ]"""


class FailingRouter:
    async def generate(self, **kwargs: object) -> str:
        raise RuntimeError("LLM unavailable")


class TestUnstructuredExtraction:
    @pytest.mark.asyncio
    async def test_mocked_llm_response_produces_key_values(self) -> None:
        extracted = await extract_unstructured(
            _document(DocumentType.PDF), MockRouter()
        )  # type: ignore[arg-type]

        assert extracted.extraction_method == "llm_assisted"
        assert extracted.key_values is not None
        assert extracted.key_values[0].field == "payment_threshold"
        assert extracted.key_values[0].value == "€10,000"

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_key_values(self) -> None:
        extracted = await extract_unstructured(
            _document(DocumentType.PDF), FailingRouter()
        )  # type: ignore[arg-type]

        assert extracted.key_values == []

    @pytest.mark.asyncio
    async def test_docx_tables_are_extracted_before_prose(self) -> None:
        document = ParsedDocument(
            doc_id="document-2",
            filename="policy.docx",
            doc_type=DocumentType.DOCX,
            content_chunks=[
                ContentChunk(
                    text="Policy applies in 2025.",
                    source_ref="policy.docx:paragraph:1",
                    chunk_index=0,
                ),
                ContentChunk(
                    text="KONTO | BETRAG",
                    source_ref="policy.docx:table:1:row:1",
                    chunk_index=1,
                ),
                ContentChunk(
                    text="1200 | 50000,00",
                    source_ref="policy.docx:table:1:row:2",
                    chunk_index=2,
                ),
            ],
        )

        extracted = await extract_unstructured(document, MockRouter())  # type: ignore[arg-type]

        assert extracted.extraction_method == "deterministic_and_llm"
        assert extracted.rows is not None
        assert extracted.rows[0]["amount"] == "50000,00"
        assert extracted.key_values is not None
