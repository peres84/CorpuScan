from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.structured import (
    extract_tabular,
    normalize_column_name,
    suggest_normalized_columns,
)


def _document(
    *, doc_type: DocumentType, filename: str, chunks: list[tuple[str, str]]
) -> ParsedDocument:
    delimiter = "\t" if doc_type is DocumentType.TXT and "\t" in chunks[0][0] else ";"
    return ParsedDocument(
        doc_id="document-1",
        filename=filename,
        doc_type=doc_type,
        content_chunks=[
            ContentChunk(text=text, source_ref=source_ref, chunk_index=index)
            for index, (text, source_ref) in enumerate(chunks)
        ],
        metadata={"delimiter": delimiter},
    )


class TestTabularExtraction:
    def test_csv_extraction_produces_correct_rows_and_columns(self) -> None:
        document = _document(
            doc_type=DocumentType.CSV,
            filename="ledger.csv",
            chunks=[
                ("KREDITOR;BETRAG_EUR;DATUM", "ledger.csv:row:1"),
                ("209101;50000,00;15.06.2025", "ledger.csv:row:2"),
            ],
        )

        extracted = extract_tabular(document)

        assert extracted.columns == ["KREDITOR", "BETRAG_EUR", "DATUM"]
        assert extracted.original_columns == extracted.columns
        assert extracted.normalized_columns == ["vendor_id", "amount", "date"]
        assert extracted.rows == [
            {
                "KREDITOR": "209101",
                "vendor_id": "209101",
                "BETRAG_EUR": "50000,00",
                "amount": "50000,00",
                "DATUM": "15.06.2025",
                "date": "15.06.2025",
            }
        ]
        assert extracted.row_count == 1

    def test_xlsx_chunks_use_the_first_text_row_as_headers(self) -> None:
        document = _document(
            doc_type=DocumentType.XLSX,
            filename="balances.xlsx",
            chunks=[
                (";", "balances.xlsx:Sheet1:row:1"),
                ("KONTO;BETRAG", "balances.xlsx:Sheet1:row:2"),
                ("1200;300,00", "balances.xlsx:Sheet1:row:3"),
            ],
        )

        extracted = extract_tabular(document)

        assert extracted.original_columns == ["KONTO", "BETRAG"]
        assert extracted.rows == [{"KONTO": "1200", "account_id": "1200", "BETRAG": "300,00", "amount": "300,00"}]

    def test_column_normalization_maps_known_synonyms(self) -> None:
        assert normalize_column_name("BETRAG_EUR") == "amount"
        assert normalize_column_name(" datum ") == "date"
        assert normalize_column_name("KREDITOR") == "vendor_id"

    def test_column_normalization_handles_variants_and_unknown_columns(self) -> None:
        assert normalize_column_name("Betrag  EUR") == "amount"
        assert normalize_column_name("WERTSTELLUNG") == "date"
        assert normalize_column_name("Custom Field") == "Custom Field"

    @pytest.mark.asyncio
    async def test_unknown_column_suggestions_are_batched(self) -> None:
        class MockRouter:
            async def generate(self, **kwargs: object) -> str:
                return '{"Kostenstelle": "cost_center", "Steuerschluessel": "tax_code"}'

        suggestions = await suggest_normalized_columns(
            ["BETRAG_EUR", "Kostenstelle", "Steuerschluessel"], MockRouter()  # type: ignore[arg-type]
        )

        assert suggestions == {"Kostenstelle": "cost_center", "Steuerschluessel": "tax_code"}

    def test_gdpdu_semicolon_txt_extracts_correctly(self) -> None:
        document = _document(
            doc_type=DocumentType.TXT,
            filename="Buchungen.txt",
            chunks=[
                ("BELEGNUMMER;KREDITOR;BUCHUNGSBETRAG", "Buchungen.txt:row:1"),
                ("ER900850;209101;50000,00", "Buchungen.txt:row:2"),
            ],
        )

        extracted = extract_tabular(document)

        assert extracted.normalized_columns == ["invoice_number", "vendor_id", "amount"]
        assert extracted.rows is not None
        assert extracted.rows[0]["invoice_number"] == "ER900850"
        assert extracted.rows[0]["amount"] == "50000,00"
