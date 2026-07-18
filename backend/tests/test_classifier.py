from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation.classifier import (
    FraudClassifierInput,
    FraudClassifierOutput,
    classify_documents,
)
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument


def _make_doc(content: str) -> ParsedDocument:
    return ParsedDocument(
        doc_id="test",
        filename="test.csv",
        doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text=content, source_ref="test.csv:row:1", chunk_index=0)],
    )


class TestFraudClassifier:
    def test_output_probability_between_0_and_1(self) -> None:
        doc = _make_doc("normal content without any suspicious patterns")
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        assert 0.0 <= result.probability <= 1.0
        assert result.label == "model signal, not evidence"

    def test_round_amounts_detected(self) -> None:
        content = (
            "209101;Ratio Consulting GmbH;50000,00;EUR\n"
            "209101;Ratio Consulting GmbH;48000,00;EUR\n"
            "209101;Ratio Consulting GmbH;50000,00;EUR\n"
            "209101;Ratio Consulting GmbH;50000,00;EUR\n"
        )
        doc = _make_doc(content)
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        assert result.probability > 0.0
        assert any("round" in s.lower() for s in result.signals)

    def test_threshold_splitting_detected(self) -> None:
        content = (
            "14.10.2025;200007;Castor Papier GmbH;9780,00\n"
            "14.10.2025;200007;Castor Papier GmbH;9820,00\n"
            "14.10.2025;200007;Castor Papier GmbH;9750,00\n"
            "14.10.2025;200007;Castor Papier GmbH;9690,00\n"
        )
        doc = _make_doc(content)
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        assert result.probability > 0.0
        assert any("threshold" in s.lower() for s in result.signals)

    def test_timing_anomaly_detected(self) -> None:
        content = (
            "15.12.2025;Lieferung Material;Rechnung offen\n"
            "20.12.2025;Lieferung Teile;Rechnung offen\n"
            "05.01.2026;Buchung ER;50000\n"
            "08.01.2026;Buchung ER;30000\n"
        )
        doc = _make_doc(content)
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        assert result.probability > 0.0
        assert any("cut-off" in s.lower() or "dec" in s.lower() for s in result.signals)

    def test_clean_document_low_probability(self) -> None:
        content = (
            "01.03.2025;200035;Fokus Handel GmbH;61802,00;Material\n"
            "15.04.2025;200097;Saturn Distribution e.K.;57656,00;Material\n"
            "22.06.2025;200023;Orion Werkstoffe SE;70544,00;Material\n"
        )
        doc = _make_doc(content)
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        # Non-round, non-threshold amounts, no timing issues
        assert result.probability < 0.5

    def test_output_is_labeled_as_signal(self) -> None:
        doc = _make_doc("anything")
        result = classify_documents(FraudClassifierInput(documents=[doc]))
        assert isinstance(result, FraudClassifierOutput)
        assert result.label == "model signal, not evidence"
        assert isinstance(result.signals, list)
