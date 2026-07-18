from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.prioritization import (
    compute_priority_score,
    rank_documents_by_priority,
    select_start_documents,
)


def _make_doc(
    doc_id: str,
    filename: str,
    doc_type: DocumentType = DocumentType.CSV,
    content: str = "generic content",
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=doc_type,
        content_chunks=[ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)],
    )


class TestPriorityScoring:
    def test_invoice_file_scores_higher_than_metadata(self) -> None:
        invoice = _make_doc("d1", "Lieferantenbuchungen.txt", DocumentType.TXT, "Betrag EUR 50000")
        metadata = _make_doc("d2", "index.xml", DocumentType.XML, "DataSet Version")

        score_invoice = compute_priority_score(invoice)
        score_metadata = compute_priority_score(metadata)

        assert score_invoice > score_metadata

    def test_bank_statement_scores_higher_than_schema(self) -> None:
        bank = _make_doc("d1", "Sachkontobuchungen.txt", DocumentType.TXT, "Zahlung Betrag Konto")
        schema = _make_doc("d2", "gdpdu-01-08-2002.dtd", DocumentType.UNKNOWN, "<!DOCTYPE>")

        score_bank = compute_priority_score(bank)
        score_schema = compute_priority_score(schema)

        assert score_bank > score_schema

    def test_financial_content_boosts_score(self) -> None:
        financial = _make_doc("d1", "data.csv", DocumentType.CSV, "EUR 48000 Zahlung Konto Betrag Rechnung")
        generic = _make_doc("d2", "data.csv", DocumentType.CSV, "hello world nothing here")

        score_financial = compute_priority_score(financial)
        score_generic = compute_priority_score(generic)

        assert score_financial > score_generic

    def test_wareneingangsliste_ranks_high(self) -> None:
        doc = _make_doc("d1", "Wareneingangsliste_2025.csv", DocumentType.CSV, "Wareneingang Material EUR")
        score = compute_priority_score(doc)
        assert score > 0.5

    def test_score_between_0_and_1(self) -> None:
        docs = [
            _make_doc("d1", "index.xml", DocumentType.XML, "version"),
            _make_doc("d2", "Lieferantenbuchungen.txt", DocumentType.TXT, "EUR Betrag"),
            _make_doc("d3", "Pruefungsplanung_JET_2025.docx", DocumentType.DOCX, "Prüfung"),
        ]
        for doc in docs:
            score = compute_priority_score(doc)
            assert 0.0 <= score <= 1.0


class TestRanking:
    def test_rank_documents_by_priority(self) -> None:
        docs = [
            _make_doc("low", "index.xml", DocumentType.XML, "schema"),
            _make_doc("high", "Lieferantenbuchungen.txt", DocumentType.TXT, "Zahlung EUR Betrag Konto"),
            _make_doc("mid", "Saldenliste_2025.xlsx", DocumentType.XLSX, "Saldo Konto"),
        ]

        ranked = rank_documents_by_priority(docs)
        filenames = [d.filename for d in ranked]

        # Lieferantenbuchungen should be first (high-priority keywords + financial content)
        assert filenames[0] == "Lieferantenbuchungen.txt"
        # index.xml should be last
        assert filenames[-1] == "index.xml"

    def test_select_start_documents(self) -> None:
        docs = [
            _make_doc("a", "index.xml", DocumentType.XML),
            _make_doc("b", "Sachkontobuchungen.txt", DocumentType.TXT, "Buchung Betrag EUR"),
            _make_doc("c", "Wareneingangsliste_2025.csv", DocumentType.CSV, "Wareneingang EUR"),
            _make_doc("d", "report.pdf", DocumentType.PDF),
        ]

        start_ids = select_start_documents(docs, max_start_docs=2)

        assert len(start_ids) == 2
        # High-priority docs should be selected
        assert "b" in start_ids or "c" in start_ids
        # Low-priority schema file should NOT be in top 2
        assert "a" not in start_ids
