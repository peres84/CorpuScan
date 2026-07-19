from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.chunker import chunk_document
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.parsers import (
    detect_document_type,
    parse_csv,
    parse_docx,
    parse_gdpdu_index,
    parse_pdf,
    parse_txt,
    parse_xlsx,
)
from app.investigation.scanner import scan_directory

DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "fraud_train_dataset"


class TestDetectDocumentType:
    def test_txt(self) -> None:
        assert detect_document_type(Path("foo.txt")) == DocumentType.TXT

    def test_pdf(self) -> None:
        assert detect_document_type(Path("report.pdf")) == DocumentType.PDF

    def test_xlsx(self) -> None:
        assert detect_document_type(Path("data.xlsx")) == DocumentType.XLSX

    def test_csv(self) -> None:
        assert detect_document_type(Path("export.csv")) == DocumentType.CSV

    def test_docx(self) -> None:
        assert detect_document_type(Path("plan.docx")) == DocumentType.DOCX

    def test_xml(self) -> None:
        assert detect_document_type(Path("index.xml")) == DocumentType.XML

    def test_unknown(self) -> None:
        assert detect_document_type(Path("image.png")) == DocumentType.UNKNOWN


class TestParseTxt:
    @pytest.mark.skipif(not (DATASET_ROOT / "AV" / "Anlagen.txt").exists(), reason="Dataset missing")
    def test_parse_anlagen(self) -> None:
        path = DATASET_ROOT / "AV" / "Anlagen.txt"
        doc = parse_txt(path)
        assert doc.doc_type == DocumentType.TXT
        assert doc.filename == "Anlagen.txt"
        assert len(doc.content_chunks) > 0
        assert doc.metadata["delimiter"] == ";"
        # Each chunk should reference the file and row
        assert "Anlagen.txt:row:" in doc.content_chunks[0].source_ref


class TestParseGdpduIndex:
    @pytest.mark.skipif(not (DATASET_ROOT / "AV" / "index.xml").exists(), reason="Dataset missing")
    def test_parse_av_index(self) -> None:
        path = DATASET_ROOT / "AV" / "index.xml"
        doc = parse_gdpdu_index(path)
        assert doc.doc_type == DocumentType.XML
        assert "supplier_name" in doc.metadata
        assert "tables" in doc.metadata
        assert len(doc.content_chunks) >= 2  # Anlagen + Anlagenbuchungen


class TestParsePdf:
    @pytest.mark.skipif(
        not (DATASET_ROOT / "Begleitdokumente" / "Exportprotokoll_GDPdU_2025.pdf").exists(),
        reason="Dataset missing",
    )
    def test_parse_pdf(self) -> None:
        path = DATASET_ROOT / "Begleitdokumente" / "Exportprotokoll_GDPdU_2025.pdf"
        doc = parse_pdf(path)
        assert doc.doc_type == DocumentType.PDF
        assert doc.page_count > 0
        assert len(doc.content_chunks) > 0


class TestParseXlsx:
    @pytest.mark.skipif(
        not (DATASET_ROOT / "Begleitdokumente" / "Saldenliste_2025.xlsx").exists(),
        reason="Dataset missing",
    )
    def test_parse_xlsx(self) -> None:
        path = DATASET_ROOT / "Begleitdokumente" / "Saldenliste_2025.xlsx"
        doc = parse_xlsx(path)
        assert doc.doc_type == DocumentType.XLSX
        assert len(doc.content_chunks) > 0


class TestParseCsv:
    @pytest.mark.skipif(
        not (DATASET_ROOT / "Begleitdokumente" / "Stammdatenaenderungen_2025.csv").exists(),
        reason="Dataset missing",
    )
    def test_parse_csv(self) -> None:
        path = DATASET_ROOT / "Begleitdokumente" / "Stammdatenaenderungen_2025.csv"
        doc = parse_csv(path)
        assert doc.doc_type == DocumentType.CSV
        assert len(doc.content_chunks) > 0
        assert doc.metadata["delimiter"] == ";"


class TestParseDocx:
    @pytest.mark.skipif(
        not (DATASET_ROOT / "Begleitdokumente" / "Pruefungsplanung_JET_2025.docx").exists(),
        reason="Dataset missing",
    )
    def test_parse_docx(self) -> None:
        path = DATASET_ROOT / "Begleitdokumente" / "Pruefungsplanung_JET_2025.docx"
        doc = parse_docx(path)
        assert doc.doc_type == DocumentType.DOCX
        assert len(doc.content_chunks) > 0


class TestChunker:
    def test_small_chunks_unchanged(self) -> None:
        doc = ParsedDocument(
            doc_id="test123",
            filename="test.txt",
            doc_type=DocumentType.TXT,
            content_chunks=[
                ContentChunk(text="short text", source_ref="test.txt:row:1", chunk_index=0),
            ],
        )
        result = chunk_document(doc, chunk_size=1500, overlap=200)
        assert len(result.content_chunks) == 1

    def test_large_chunk_split(self) -> None:
        long_text = "word " * 500  # ~2500 chars
        doc = ParsedDocument(
            doc_id="test456",
            filename="big.txt",
            doc_type=DocumentType.TXT,
            content_chunks=[
                ContentChunk(text=long_text.strip(), source_ref="big.txt:row:1", chunk_index=0),
            ],
        )
        result = chunk_document(doc, chunk_size=500, overlap=100)
        assert len(result.content_chunks) > 1
        # All chunks should have proper source refs
        for chunk in result.content_chunks:
            assert "big.txt:row:1:chunk:" in chunk.source_ref


class TestScanDirectory:
    @pytest.mark.skipif(not DATASET_ROOT.exists(), reason="Dataset missing")
    def test_scan_all_files_parsed(self) -> None:
        """Integration test: scan fraud_train_dataset/, assert all files parsed without error."""
        documents = scan_directory(DATASET_ROOT)
        assert len(documents) > 0

        # Verify we have documents from multiple subdirectories
        filenames = {doc.filename for doc in documents}
        assert "Anlagen.txt" in filenames
        assert "Anlagenbuchungen.txt" in filenames
        assert "Stammdatenaenderungen_2025.csv" in filenames

        # Verify no document has empty chunks (except possibly unknown types)
        for doc in documents:
            if doc.doc_type != DocumentType.UNKNOWN:
                assert len(doc.content_chunks) > 0, f"{doc.filename} has no chunks"

        # Verify doc_ids are unique
        doc_ids = [doc.doc_id for doc in documents]
        assert len(doc_ids) == len(set(doc_ids))

    @pytest.mark.skipif(not DATASET_ROOT.exists(), reason="Dataset missing")
    def test_expected_file_count(self) -> None:
        """Verify we parse all expected files in the dataset."""
        documents = scan_directory(DATASET_ROOT)
        # Dataset has: AV(3 parseable), Sachkonten(3), Kreditoren(3), Debitoren(3),
        # Begleitdokumente(~19 files), minus DTD files
        # Total parseable: roughly 28+ files
        assert len(documents) >= 25
