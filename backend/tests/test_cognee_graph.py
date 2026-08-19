from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cognee.graph import (
    _normalize_entity_type,
    _parse_cognee_graph_result,
    merge_cognee_into_document_graph,
    merge_cognee_into_evidence_store,
)
from app.cognee.schemas import CogneeEntity, CogneeGraphResponse, CogneeRelationship
from app.investigation.evidence_store import Entity, EvidenceStore
from app.investigation.graph import DocumentGraph


class TestParseGraphResult:
    def test_parse_nodes_edges_format(self) -> None:
        result = {
            "nodes": [
                {"name": "Ratio Consulting GmbH", "type": "company"},
                {"name": "MV-U05", "type": "person"},
            ],
            "edges": [
                {
                    "source": "MV-U05",
                    "target": "Ratio Consulting GmbH",
                    "type": "created",
                },
            ],
        }
        response = _parse_cognee_graph_result(result)
        assert len(response.entities) == 2
        assert len(response.relationships) == 1
        assert response.entities[0].name == "Ratio Consulting GmbH"
        assert response.relationships[0].relationship_type == "created"

    def test_parse_entities_relationships_format(self) -> None:
        result = {
            "entities": [
                {"name": "209101", "type": "account"},
            ],
            "relationships": [
                {
                    "source": "209101",
                    "target": "Ratio Consulting GmbH",
                    "type": "belongs_to",
                },
            ],
        }
        response = _parse_cognee_graph_result(result)
        assert len(response.entities) == 1
        assert len(response.relationships) == 1

    def test_parse_empty_result(self) -> None:
        response = _parse_cognee_graph_result(None)
        assert response.entities == []
        assert response.relationships == []

    def test_parse_list_result(self) -> None:
        result = [
            {"nodes": [{"name": "Entity1", "type": "vendor"}], "edges": []},
        ]
        response = _parse_cognee_graph_result(result)
        assert len(response.entities) == 1


class TestNormalizeEntityType:
    def test_maps_company_to_vendor(self) -> None:
        assert _normalize_entity_type("company") == "vendor"
        assert _normalize_entity_type("organization") == "vendor"

    def test_maps_user_to_person(self) -> None:
        assert _normalize_entity_type("user") == "person"
        assert _normalize_entity_type("Person") == "person"

    def test_unknown_passes_through(self) -> None:
        assert _normalize_entity_type("custom_type") == "custom_type"


class TestMergeIntoEvidenceStore:
    def test_adds_new_entities(self) -> None:
        store = EvidenceStore()
        response = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Vendor A", entity_type="vendor"),
                CogneeEntity(name="€50,000", entity_type="amount"),
            ],
            relationships=[],
        )

        added = merge_cognee_into_evidence_store(response, store)

        assert added == 2
        assert store.entity_count == 2
        assert store.get_entity("Vendor A") is not None

    def test_deduplicates_existing_entities(self) -> None:
        store = EvidenceStore()
        # Pre-existing entity
        store.add_entity(
            Entity(name="Vendor A", entity_type="vendor", source_doc_id="doc1")
        )

        response = CogneeGraphResponse(
            entities=[
                CogneeEntity(name="Vendor A", entity_type="vendor"),
                CogneeEntity(name="New Entity", entity_type="account"),
            ],
            relationships=[],
        )

        added = merge_cognee_into_evidence_store(response, store)

        # Only 1 new (New Entity), Vendor A was deduplicated
        assert added == 1
        assert store.entity_count == 2

    def test_empty_response_adds_nothing(self) -> None:
        store = EvidenceStore()
        response = CogneeGraphResponse()
        added = merge_cognee_into_evidence_store(response, store)
        assert added == 0


class TestMergeIntoDocumentGraph:
    def test_adds_edges_for_related_entities(self) -> None:
        graph = DocumentGraph()
        store = EvidenceStore()

        graph.add_document("doc1", "invoice.csv")
        graph.add_document("doc2", "payments.csv")

        # doc1 contains entity "VendorX", doc2 contains entity "VendorX"
        entity = Entity(name="VendorX", entity_type="vendor", source_doc_id="doc1")
        graph.add_entity_to_document("doc1", entity)
        entity2 = Entity(name="VendorX", entity_type="vendor", source_doc_id="doc2")
        graph.add_entity_to_document("doc2", entity2)

        # Cognee finds a relationship between VendorX and AccountY
        response = CogneeGraphResponse(
            entities=[],
            relationships=[
                CogneeRelationship(
                    source_entity="VendorX",
                    target_entity="AccountY",
                    relationship_type="paid_via",
                ),
            ],
        )

        # AccountY doesn't exist in graph yet, so no edges should be added
        added = merge_cognee_into_document_graph(response, graph, store)
        assert added == 0

    def test_creates_edges_when_both_entities_in_graph(self) -> None:
        graph = DocumentGraph()
        store = EvidenceStore()

        graph.add_document("doc1", "invoice.csv")
        graph.add_document("doc2", "permissions.csv")

        entity_a = Entity(name="MV-U05", entity_type="person", source_doc_id="doc1")
        graph.add_entity_to_document("doc1", entity_a)
        entity_b = Entity(name="209101", entity_type="account", source_doc_id="doc2")
        graph.add_entity_to_document("doc2", entity_b)

        response = CogneeGraphResponse(
            entities=[],
            relationships=[
                CogneeRelationship(
                    source_entity="MV-U05",
                    target_entity="209101",
                    relationship_type="created",
                ),
            ],
        )

        added = merge_cognee_into_document_graph(response, graph, store)
        # doc1 has MV-U05, doc2 has 209101 — should create edge between them
        assert added >= 1
