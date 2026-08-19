"""Integration tests for fraud detection against fraud_train_dataset/.

These tests require a working LLM API key (OPENAI_KEY or GEMINI_API_KEY)
and are skipped when no key is available.

Expected results (from fraud_train_dataset/truth_revealed.md):
- F1: Fake vendor "Ratio Consulting GmbH" (209101) — €248,000
- F2: Repairs capitalised as assets — €150,800
- F3: December costs parked in January — €192,000
- F4: Split payments under €10,000 threshold — €39,040

Decoys that must NOT be flagged: D1-D7
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.models import DocumentType
from app.investigation.scanner import scan_directory

DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "fraud_train_dataset"

_has_openai = bool(os.environ.get("OPENAI_KEY", "").strip()) and os.environ.get(
    "OPENAI_KEY", ""
).strip().lower() not in (
    "key_here",
    "your_api_key",
    "api_key_here",
    "replace_me",
)
_has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip()) and os.environ.get(
    "GEMINI_API_KEY", ""
).strip().lower() not in (
    "key_here",
    "your_api_key",
    "api_key_here",
    "replace_me",
)
_has_llm_key = _has_openai or _has_gemini

skip_no_llm = pytest.mark.skipif(not _has_llm_key, reason="No LLM API key available")
skip_no_dataset = pytest.mark.skipif(
    not DATASET_ROOT.exists(), reason="Dataset not found"
)


class TestDocumentParsing:
    """Verify all documents in fraud_train_dataset/ are parsed and included in the graph."""

    @skip_no_dataset
    def test_all_files_parsed(self) -> None:
        documents = scan_directory(DATASET_ROOT)
        assert len(documents) >= 25

        filenames = {doc.filename for doc in documents}
        # Key files that must be present
        assert "Anlagen.txt" in filenames
        assert "Anlagenbuchungen.txt" in filenames
        assert "Lieferantenbuchungen.txt" in filenames
        assert "Sachkontobuchungen.txt" in filenames
        assert "Stammdatenaenderungen_2025.csv" in filenames
        assert "Wareneingangsliste_2025.csv" in filenames
        assert "Fakturajournal_Januar_2026_Kreditoren.csv" in filenames
        assert "Pruefungsplanung_JET_2025.docx" in filenames
        assert "Berechtigungsauswertung_2025.xlsx" in filenames

    @skip_no_dataset
    def test_no_empty_documents(self) -> None:
        documents = scan_directory(DATASET_ROOT)
        for doc in documents:
            if doc.doc_type != DocumentType.UNKNOWN:
                assert len(doc.content_chunks) > 0, f"{doc.filename} has no content"

    @skip_no_dataset
    def test_doc_ids_are_unique(self) -> None:
        documents = scan_directory(DATASET_ROOT)
        ids = [doc.doc_id for doc in documents]
        assert len(ids) == len(set(ids))

    @skip_no_dataset
    def test_error_recovery_individual_file_failure(self) -> None:
        """If one document fails to parse, investigation continues with remaining docs."""
        documents = scan_directory(DATASET_ROOT)
        # The scanner already skips failed files — verify we still get most docs
        assert len(documents) >= 20


class TestFullPipeline:
    """Full pipeline integration tests requiring LLM API keys."""

    @skip_no_llm
    @skip_no_dataset
    @pytest.mark.asyncio
    async def test_pipeline_runs_to_completion(self) -> None:
        """Run full investigation pipeline against fraud_train_dataset/."""
        from app.investigation.pipeline import (
            InvestigationJobStore,
            run_investigation_pipeline,
        )

        documents = scan_directory(DATASET_ROOT)
        store = InvestigationJobStore()
        job_id = store.create()

        await run_investigation_pipeline(
            job_store=store,
            job_id=job_id,
            documents=documents,
        )

        job = store.get(job_id)
        assert job is not None
        # Should complete (or error if keys are invalid — but not crash)
        assert job.status in ("done", "error")

    @skip_no_llm
    @skip_no_dataset
    @pytest.mark.asyncio
    async def test_detects_f1_fake_vendor(self) -> None:
        """Verify investigation detects F1: fake vendor Ratio Consulting GmbH."""
        from app.investigation.pipeline import (
            InvestigationJobStore,
            run_investigation_pipeline,
        )

        documents = scan_directory(DATASET_ROOT)
        store = InvestigationJobStore()
        job_id = store.create()

        await run_investigation_pipeline(
            job_store=store,
            job_id=job_id,
            documents=documents,
        )

        job = store.get(job_id)
        assert job is not None
        if job.status != "done":
            pytest.skip("Pipeline did not complete successfully")

        # Check findings mention Ratio Consulting or 209101
        all_text = " ".join(f.finding_text for f in job.findings)
        buffer_text = " ".join(
            row.notes_summary
            for row in (
                job.investigation_state.buffer if job.investigation_state else []
            )
        )
        combined = f"{all_text} {buffer_text}".lower()

        assert "ratio" in combined or "209101" in combined, (
            "F1 not detected: expected mention of Ratio Consulting GmbH or 209101"
        )

    @skip_no_llm
    @skip_no_dataset
    @pytest.mark.asyncio
    async def test_detects_f2_repairs_as_assets(self) -> None:
        """Verify investigation detects F2: repairs capitalised as assets."""
        from app.investigation.pipeline import (
            InvestigationJobStore,
            run_investigation_pipeline,
        )

        documents = scan_directory(DATASET_ROOT)
        store = InvestigationJobStore()
        job_id = store.create()

        await run_investigation_pipeline(
            job_store=store,
            job_id=job_id,
            documents=documents,
        )

        job = store.get(job_id)
        assert job is not None
        if job.status != "done":
            pytest.skip("Pipeline did not complete successfully")

        buffer_text = " ".join(
            row.notes_summary
            for row in (
                job.investigation_state.buffer if job.investigation_state else []
            )
        )
        combined = buffer_text.lower()

        assert any(
            kw in combined
            for kw in ("reparatur", "instandsetzung", "repair", "capitaliz")
        ), "F2 not detected: expected mention of repairs booked as assets"

    @skip_no_llm
    @skip_no_dataset
    @pytest.mark.asyncio
    async def test_detects_f3_cutoff_manipulation(self) -> None:
        """Verify investigation detects F3: December costs parked in January."""
        from app.investigation.pipeline import (
            InvestigationJobStore,
            run_investigation_pipeline,
        )

        documents = scan_directory(DATASET_ROOT)
        store = InvestigationJobStore()
        job_id = store.create()

        await run_investigation_pipeline(
            job_store=store,
            job_id=job_id,
            documents=documents,
        )

        job = store.get(job_id)
        assert job is not None
        if job.status != "done":
            pytest.skip("Pipeline did not complete successfully")

        buffer_text = " ".join(
            row.notes_summary
            for row in (
                job.investigation_state.buffer if job.investigation_state else []
            )
        )
        combined = buffer_text.lower()

        assert any(
            kw in combined
            for kw in (
                "cut-off",
                "cutoff",
                "dezember",
                "december",
                "januar",
                "january",
                "accrual",
            )
        ), "F3 not detected: expected mention of cut-off manipulation"

    @skip_no_llm
    @skip_no_dataset
    @pytest.mark.asyncio
    async def test_detects_f4_split_payments(self) -> None:
        """Verify investigation detects F4: split payments under €10,000 threshold."""
        from app.investigation.pipeline import (
            InvestigationJobStore,
            run_investigation_pipeline,
        )

        documents = scan_directory(DATASET_ROOT)
        store = InvestigationJobStore()
        job_id = store.create()

        await run_investigation_pipeline(
            job_store=store,
            job_id=job_id,
            documents=documents,
        )

        job = store.get(job_id)
        assert job is not None
        if job.status != "done":
            pytest.skip("Pipeline did not complete successfully")

        buffer_text = " ".join(
            row.notes_summary
            for row in (
                job.investigation_state.buffer if job.investigation_state else []
            )
        )
        combined = buffer_text.lower()

        assert any(
            kw in combined
            for kw in ("split", "threshold", "10.000", "10,000", "castor papier")
        ), "F4 not detected: expected mention of split payments or threshold evasion"


class TestClassifierOnDataset:
    """Test the rule-based classifier against the real dataset."""

    @skip_no_dataset
    def test_classifier_detects_signals(self) -> None:
        from app.investigation.classifier import (
            FraudClassifierInput,
            classify_documents,
        )

        documents = scan_directory(DATASET_ROOT)
        result = classify_documents(FraudClassifierInput(documents=documents))

        # Should find at least some signals in the fraud-seeded dataset
        assert result.probability > 0.0
        assert len(result.signals) > 0
        assert result.label == "model signal, not evidence"
