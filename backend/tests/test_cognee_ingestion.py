from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.cognee.client import CogneeClient
from app.cognee.ingestion import (
    _build_ingestion_text,
    get_node_set,
    ingest_documents,
)
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument


def _make_doc(
    doc_id: str = "d1",
    filename: str = "test.csv",
    doc_type: DocumentType = DocumentType.CSV,
    content: str = "test content",
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=doc_type,
        content_chunks=[ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)],
    )


class TestNodeSetAssignment:
    def test_vendor_file_gets_vendor_node_set(self) -> None:
        doc = _make_doc(filename="Lieferantenbuchungen.txt", doc_type=DocumentType.TXT)
        assert get_node_set(doc) == "vendor_records"

    def test_receipt_file_gets_receipts_node_set(self) -> None:
        doc = _make_doc(filename="Wareneingangsliste_2025.csv", doc_type=DocumentType.CSV)
        assert get_node_set(doc) == "receipts"

    def test_permission_file_gets_permissions_node_set(self) -> None:
        doc = _make_doc(filename="Berechtigungsauswertung_2025.xlsx", doc_type=DocumentType.XLSX)
        assert get_node_set(doc) == "permissions"

    def test_accounting_file_gets_ledgers_node_set(self) -> None:
        doc = _make_doc(filename="Sachkontobuchungen.txt", doc_type=DocumentType.TXT)
        assert get_node_set(doc) == "accounting_ledgers"

    def test_stammdaten_gets_master_data(self) -> None:
        doc = _make_doc(filename="Stammdatenaenderungen_2025.csv", doc_type=DocumentType.CSV)
        assert get_node_set(doc) == "master_data"

    def test_pdf_defaults_to_reports(self) -> None:
        doc = _make_doc(filename="some_report.pdf", doc_type=DocumentType.PDF)
        assert get_node_set(doc) == "reports"

    def test_xml_defaults_to_metadata(self) -> None:
        doc = _make_doc(filename="index.xml", doc_type=DocumentType.XML)
        assert get_node_set(doc) == "metadata"


class TestBuildIngestionText:
    def test_includes_metadata_header(self) -> None:
        doc = _make_doc(filename="test.csv", content="row data here")
        text = _build_ingestion_text(doc)
        assert "Document: test.csv" in text
        assert "Type: csv" in text
        assert "row data here" in text

    def test_truncates_large_content(self) -> None:
        long_content = "x" * 20000
        doc = _make_doc(content=long_content)
        text = _build_ingestion_text(doc)
        assert len(text) <= 15200  # _MAX_CONTENT_PER_DOC + header


class TestIngestDocuments:
    @pytest.mark.asyncio
    async def test_skips_when_client_unavailable(self) -> None:
        client = CogneeClient()
        # Never initialized — unavailable
        docs = [_make_doc()]
        count = await ingest_documents(client, docs)
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingests_documents_via_cognee(self) -> None:
        """Verify documents are passed to cognee.remember() with correct node sets."""
        client = CogneeClient()
        client._available = True

        docs = [
            _make_doc("d1", "Lieferantenbuchungen.txt", DocumentType.TXT, "vendor data"),
            _make_doc("d2", "Wareneingangsliste_2025.csv", DocumentType.CSV, "receipt data"),
            _make_doc("d3", "report.pdf", DocumentType.PDF, "report content"),
        ]

        mock_remember = AsyncMock()
        mock_cognee = MagicMock()
        mock_cognee.remember = mock_remember

        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            count = await ingest_documents(client, docs)

        assert count == 3
        assert mock_remember.call_count == 3
        # Verify node sets were passed correctly
        calls = mock_remember.call_args_list
        node_sets_used = [c.kwargs.get("node_set") or c[1].get("node_set") for c in calls]
        assert ["vendor_records"] in node_sets_used
        assert ["receipts"] in node_sets_used
        assert ["reports"] in node_sets_used

    @pytest.mark.asyncio
    async def test_handles_ingestion_failure_gracefully(self) -> None:
        """If one document fails ingestion, others continue."""
        client = CogneeClient()
        client._available = True

        docs = [
            _make_doc("d1", "good.csv", DocumentType.CSV, "good data"),
            _make_doc("d2", "bad.csv", DocumentType.CSV, "bad data"),
        ]

        call_count = {"n": 0}

        async def mock_remember(text, **kwargs):
            call_count["n"] += 1
            if "bad data" in text:
                raise RuntimeError("Cognee error")

        mock_cognee = MagicMock()
        mock_cognee.remember = mock_remember

        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: mock_cognee if name == "cognee" else __import__(name, *a, **kw)):
            count = await ingest_documents(client, docs)

        # One succeeded, one failed
        assert count == 1
