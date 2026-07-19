from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.evidence_store import Entity, EvidenceReference, EvidenceStore, Finding
from app.investigation.entities import _parse_entity_response, extract_entities_from_document
from app.investigation.graph import DocumentGraph
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument


class TestEvidenceStoreCRUD:
    def test_add_and_get_document(self) -> None:
        store = EvidenceStore()
        doc = ParsedDocument(
            doc_id="doc1",
            filename="test.csv",
            doc_type=DocumentType.CSV,
            content_chunks=[ContentChunk(text="row data", source_ref="test.csv:row:1", chunk_index=0)],
        )
        store.add_document(doc)
        assert store.document_count == 1
        assert store.get_document("doc1") is doc

    def test_get_missing_document_returns_none(self) -> None:
        store = EvidenceStore()
        assert store.get_document("missing") is None

    def test_list_documents(self) -> None:
        store = EvidenceStore()
        doc1 = ParsedDocument(doc_id="d1", filename="a.txt", doc_type=DocumentType.TXT)
        doc2 = ParsedDocument(doc_id="d2", filename="b.txt", doc_type=DocumentType.TXT)
        store.add_document(doc1)
        store.add_document(doc2)
        assert len(store.list_documents()) == 2

    def test_remove_document(self) -> None:
        store = EvidenceStore()
        doc = ParsedDocument(doc_id="d1", filename="a.txt", doc_type=DocumentType.TXT)
        store.add_document(doc)
        assert store.remove_document("d1") is True
        assert store.document_count == 0
        assert store.remove_document("d1") is False

    def test_add_and_get_entity(self) -> None:
        store = EvidenceStore()
        entity = Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="doc1")
        store.add_entity(entity)
        assert store.entity_count == 1
        assert store.get_entity("Ratio Consulting GmbH") is entity

    def test_get_entities_by_doc(self) -> None:
        store = EvidenceStore()
        e1 = Entity(name="Vendor A", entity_type="vendor", source_doc_id="doc1")
        e2 = Entity(name="Vendor B", entity_type="vendor", source_doc_id="doc2")
        e3 = Entity(name="€48000", entity_type="amount", source_doc_id="doc1")
        store.add_entity(e1)
        store.add_entity(e2)
        store.add_entity(e3)
        doc1_entities = store.get_entities_by_doc("doc1")
        assert len(doc1_entities) == 2
        assert all(e.source_doc_id == "doc1" for e in doc1_entities)

    def test_get_entities_by_type(self) -> None:
        store = EvidenceStore()
        store.add_entity(Entity(name="Vendor A", entity_type="vendor", source_doc_id="doc1"))
        store.add_entity(Entity(name="€48000", entity_type="amount", source_doc_id="doc1"))
        store.add_entity(Entity(name="Vendor B", entity_type="vendor", source_doc_id="doc2"))
        vendors = store.get_entities_by_type("vendor")
        assert len(vendors) == 2

    def test_add_and_get_finding(self) -> None:
        store = EvidenceStore()
        finding = Finding(
            finding_id="f1",
            finding_text="Suspicious round amounts",
            evidence=[
                EvidenceReference(
                    doc_id="doc1",
                    location="row:5",
                    passage="€50,000 payment",
                    confidence=0.85,
                )
            ],
            fraud_likelihood=0.7,
        )
        store.add_finding(finding)
        assert store.finding_count == 1
        assert store.get_finding("f1") is finding
        assert store.get_finding("missing") is None

    def test_list_findings(self) -> None:
        store = EvidenceStore()
        store.add_finding(Finding(finding_id="f1", finding_text="Finding 1"))
        store.add_finding(Finding(finding_id="f2", finding_text="Finding 2"))
        assert len(store.list_findings()) == 2


class TestDocumentGraph:
    def test_add_documents(self) -> None:
        graph = DocumentGraph()
        graph.add_document("doc1", "invoice.pdf")
        graph.add_document("doc2", "ledger.xlsx")
        assert graph.node_count == 2

    def test_shared_entity_creates_edge(self) -> None:
        graph = DocumentGraph()
        graph.add_document("doc1", "invoice.pdf")
        graph.add_document("doc2", "ledger.xlsx")

        entity1 = Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="doc1")
        entity2 = Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="doc2")

        graph.add_entity_to_document("doc1", entity1)
        graph.add_entity_to_document("doc2", entity2)

        assert graph.edge_count >= 1
        related = graph.get_related_documents("doc1")
        assert "doc2" in related

    def test_get_documents_by_entity(self) -> None:
        graph = DocumentGraph()
        graph.add_document("doc1", "a.txt")
        graph.add_document("doc2", "b.txt")
        graph.add_document("doc3", "c.txt")

        entity = Entity(name="209101", entity_type="account", source_doc_id="doc1")
        graph.add_entity_to_document("doc1", entity)
        entity2 = Entity(name="209101", entity_type="account", source_doc_id="doc3")
        graph.add_entity_to_document("doc3", entity2)

        docs = graph.get_documents_by_entity("209101")
        assert "doc1" in docs
        assert "doc3" in docs
        assert "doc2" not in docs

    def test_no_self_edges(self) -> None:
        graph = DocumentGraph()
        graph.add_document("doc1", "a.txt")
        entity = Entity(name="Test", entity_type="vendor", source_doc_id="doc1")
        graph.add_entity_to_document("doc1", entity)
        related = graph.get_related_documents("doc1")
        assert "doc1" not in related

    def test_get_shared_entities(self) -> None:
        graph = DocumentGraph()
        graph.add_document("doc1", "a.txt")
        graph.add_document("doc2", "b.txt")

        graph.add_entity_to_document("doc1", Entity(name="vendor_x", entity_type="vendor", source_doc_id="doc1"))
        graph.add_entity_to_document("doc1", Entity(name="unique_a", entity_type="amount", source_doc_id="doc1"))
        graph.add_entity_to_document("doc2", Entity(name="vendor_x", entity_type="vendor", source_doc_id="doc2"))
        graph.add_entity_to_document("doc2", Entity(name="unique_b", entity_type="amount", source_doc_id="doc2"))

        shared = graph.get_shared_entities("doc1", "doc2")
        assert "vendor_x" in shared
        assert "unique_a" not in shared
        assert "unique_b" not in shared


class TestEntityExtraction:
    def test_parse_valid_json_response(self) -> None:
        response = """[
            {"name": "Ratio Consulting GmbH", "type": "vendor", "aliases": ["209101"]},
            {"name": "€48,000", "type": "amount", "aliases": []},
            {"name": "MV-U05", "type": "person", "aliases": []}
        ]"""
        entities = _parse_entity_response(response, "doc1")
        assert len(entities) == 3
        assert entities[0].name == "Ratio Consulting GmbH"
        assert entities[0].entity_type == "vendor"
        assert "209101" in entities[0].aliases
        assert entities[0].source_doc_id == "doc1"

    def test_parse_response_with_code_fences(self) -> None:
        response = """```json
[{"name": "Test Corp", "type": "company", "aliases": []}]
```"""
        entities = _parse_entity_response(response, "doc2")
        assert len(entities) == 1
        assert entities[0].name == "Test Corp"

    def test_parse_invalid_json_returns_empty(self) -> None:
        entities = _parse_entity_response("not json at all", "doc1")
        assert entities == []

    def test_parse_empty_array(self) -> None:
        entities = _parse_entity_response("[]", "doc1")
        assert entities == []

    @pytest.mark.asyncio
    async def test_extract_entities_with_mocked_llm(self) -> None:
        """Verify entity extraction works with a mocked LLM response."""

        class MockRouter:
            async def generate(self, **kwargs: object) -> str:
                return '[{"name": "Castor Papier GmbH", "type": "vendor", "aliases": ["200007"]}]'

        doc = ParsedDocument(
            doc_id="test_doc",
            filename="payments.csv",
            doc_type=DocumentType.CSV,
            content_chunks=[
                ContentChunk(text="200007;Castor Papier GmbH;9780,00", source_ref="payments.csv:row:1", chunk_index=0),
            ],
        )

        entities = await extract_entities_from_document(doc, MockRouter())  # type: ignore[arg-type]
        assert len(entities) == 1
        assert entities[0].name == "Castor Papier GmbH"
        assert entities[0].entity_type == "vendor"
        assert entities[0].source_doc_id == "test_doc"
