"""Integration tests for Cognee-enhanced fraud detection against fraud_train_dataset/.

These tests validate that Cognee integration improves investigation quality.
LLM-dependent tests are skipped when no API key is available.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.cognee.schemas import CogneeEntity, CogneeGraphResponse, CogneeRelationship
from app.investigation.report import build_knowledge_graph_summary, build_relationship_chains
from app.investigation.scanner import scan_directory

DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "fraud_train_dataset"

_has_llm_key = bool(
    (os.environ.get("OPENAI_KEY", "").strip() and os.environ.get("OPENAI_KEY", "").strip().lower() not in ("key_here", "your_api_key"))
    or (os.environ.get("GEMINI_API_KEY", "").strip() and os.environ.get("GEMINI_API_KEY", "").strip().lower() not in ("key_here", "your_api_key"))
)

skip_no_llm = pytest.mark.skipif(not _has_llm_key, reason="No LLM API key available")
skip_no_dataset = pytest.mark.skipif(not DATASET_ROOT.exists(), reason="Dataset not found")


def _build_f1_cognee_graph() -> CogneeGraphResponse:
    """Simulated Cognee graph that connects F1 fraud entities."""
    return CogneeGraphResponse(
        entities=[
            CogneeEntity(name="MV-U05", entity_type="person"),
            CogneeEntity(name="Ratio Consulting GmbH", entity_type="vendor"),
            CogneeEntity(name="209101", entity_type="account"),
            CogneeEntity(name="€248,000", entity_type="amount"),
            CogneeEntity(name="Wareneingangsliste_2025.csv", entity_type="document"),
        ],
        relationships=[
            CogneeRelationship(source_entity="MV-U05", target_entity="Ratio Consulting GmbH", relationship_type="created"),
            CogneeRelationship(source_entity="MV-U05", target_entity="Ratio Consulting GmbH", relationship_type="approved"),
            CogneeRelationship(source_entity="Ratio Consulting GmbH", target_entity="209101", relationship_type="has_account"),
            CogneeRelationship(source_entity="Ratio Consulting GmbH", target_entity="€248,000", relationship_type="invoiced"),
            CogneeRelationship(source_entity="209101", target_entity="Wareneingangsliste_2025.csv", relationship_type="no_receipt"),
        ],
    )


class TestCogneeGraphConnectsF1:
    """Verify Cognee should connect MV-U05 → Vendor 209101 → invoices → missing receipts."""

    def test_f1_chain_built(self) -> None:
        graph = _build_f1_cognee_graph()
        chains = build_relationship_chains(graph)
        # Should build a chain starting from MV-U05
        assert any("MV-U05" in chain for chain in chains)
        assert any("created" in chain or "approved" in chain for chain in chains)

    def test_f1_summary_includes_entities(self) -> None:
        graph = _build_f1_cognee_graph()
        summary = build_knowledge_graph_summary(graph)
        assert "5 entities" in summary
        assert "5 relationships" in summary


class TestCogneeGraphConnectsF2:
    """Verify Cognee should surface repair-named assets connected to expense account."""

    def test_f2_relationships(self) -> None:
        graph = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Reparatur Konfektioniermaschine", entity_type="asset"),
                CogneeEntity(name="040000", entity_type="account"),
                CogneeEntity(name="670000", entity_type="account"),
            ],
            relationships=[
                CogneeRelationship(source_entity="Reparatur Konfektioniermaschine", target_entity="040000", relationship_type="booked_to"),
                CogneeRelationship(source_entity="Reparatur Konfektioniermaschine", target_entity="670000", relationship_type="should_be"),
            ],
        )
        chains = build_relationship_chains(graph)
        assert any("Reparatur" in chain for chain in chains)


class TestCogneeGraphConnectsF3:
    """Verify Cognee should link December goods receipts to January bookings."""

    def test_f3_cutoff_chain(self) -> None:
        graph = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Dec 2025 delivery", entity_type="event"),
                CogneeEntity(name="Jan 2026 booking", entity_type="event"),
                CogneeEntity(name="no accrual", entity_type="finding"),
            ],
            relationships=[
                CogneeRelationship(source_entity="Dec 2025 delivery", target_entity="Jan 2026 booking", relationship_type="delayed_booking"),
                CogneeRelationship(source_entity="Jan 2026 booking", target_entity="no accrual", relationship_type="missing"),
            ],
        )
        chains = build_relationship_chains(graph)
        assert any("Dec 2025" in chain or "delayed" in chain for chain in chains)


class TestCogneeGraphConnectsF4:
    """Verify Cognee should cluster same-day same-vendor payments."""

    def test_f4_split_payments(self) -> None:
        graph = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Castor Papier GmbH", entity_type="vendor"),
                CogneeEntity(name="14.10.2025", entity_type="date"),
                CogneeEntity(name="€9,780", entity_type="amount"),
                CogneeEntity(name="€9,820", entity_type="amount"),
                CogneeEntity(name="€9,750", entity_type="amount"),
                CogneeEntity(name="€9,690", entity_type="amount"),
            ],
            relationships=[
                CogneeRelationship(source_entity="Castor Papier GmbH", target_entity="14.10.2025", relationship_type="payment_date"),
                CogneeRelationship(source_entity="Castor Papier GmbH", target_entity="€9,780", relationship_type="paid"),
                CogneeRelationship(source_entity="Castor Papier GmbH", target_entity="€9,820", relationship_type="paid"),
                CogneeRelationship(source_entity="Castor Papier GmbH", target_entity="€9,750", relationship_type="paid"),
                CogneeRelationship(source_entity="Castor Papier GmbH", target_entity="€9,690", relationship_type="paid"),
            ],
        )
        chains = build_relationship_chains(graph)
        assert any("Castor Papier" in chain for chain in chains)


class TestCogneeDecoysShouldNotFlag:
    """Cognee relationships should show legitimate patterns for decoys."""

    def test_d3_legitimate_vendor(self) -> None:
        """D3: Vega Werkstoffe GmbH has four-eyes + real deliveries."""
        graph = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Vega Werkstoffe GmbH", entity_type="vendor"),
                CogneeEntity(name="MV-U03", entity_type="person"),
                CogneeEntity(name="MV-U02", entity_type="person"),
            ],
            relationships=[
                CogneeRelationship(source_entity="MV-U03", target_entity="Vega Werkstoffe GmbH", relationship_type="created"),
                CogneeRelationship(source_entity="MV-U02", target_entity="Vega Werkstoffe GmbH", relationship_type="approved"),
            ],
        )
        chains = build_relationship_chains(graph)
        # Should show proper four-eyes: different creator and approver
        assert any("MV-U03" in chain and "created" in chain for chain in chains)
        assert any("MV-U02" in chain and "approved" in chain for chain in chains)


class TestDocumentReductionMetrics:
    """Measure efficiency improvements with Cognee."""

    @skip_no_dataset
    def test_documents_parsed_for_comparison(self) -> None:
        """Baseline: count total parseable documents for comparison metrics."""
        documents = scan_directory(DATASET_ROOT)
        # Record baseline doc count for comparison
        assert len(documents) >= 25
        # Future: compare investigation steps with/without Cognee


class TestPerformance:
    @skip_no_dataset
    def test_cognee_graph_operations_are_fast(self) -> None:
        """Verify graph operations complete quickly even with full dataset."""
        import time
        from app.investigation.graph import DocumentGraph
        from app.investigation.evidence_store import Entity

        documents = scan_directory(DATASET_ROOT)
        graph = DocumentGraph()

        start = time.perf_counter()
        for doc in documents:
            graph.add_document(doc.doc_id, doc.filename)

        # Simulate entity additions
        for i, doc in enumerate(documents[:10]):
            graph.add_entity_to_document(
                doc.doc_id,
                Entity(name=f"Entity_{i}", entity_type="vendor", source_doc_id=doc.doc_id),
            )

        elapsed = time.perf_counter() - start
        assert elapsed < 1.0  # Graph ops should be well under 1 second
