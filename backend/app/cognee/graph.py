from __future__ import annotations

import logging

from app.cognee.client import CogneeClient
from app.cognee.schemas import CogneeEntity, CogneeGraphResponse, CogneeRelationship
from app.investigation.evidence_store import Entity, EvidenceStore
from app.investigation.graph import DocumentGraph

logger = logging.getLogger(__name__)

# Map Cognee entity labels to our internal entity types
_ENTITY_TYPE_MAPPING: dict[str, str] = {
    "company": "vendor",
    "organization": "vendor",
    "person": "person",
    "user": "person",
    "amount": "amount",
    "money": "amount",
    "account": "account",
    "date": "date",
    "invoice": "invoice_number",
    "document": "invoice_number",
}


async def build_knowledge_graph(client: CogneeClient) -> CogneeGraphResponse:
    """Call cognee.memify() to enrich the knowledge graph, then extract entities and relationships.

    Returns a CogneeGraphResponse with discovered entities and relationships.
    If Cognee is unavailable, returns an empty response.
    """
    if not client.is_available():
        return CogneeGraphResponse()

    try:
        import cognee

        # Run enrichment pipeline
        await cognee.memify()
        logger.info("Cognee memify() completed — knowledge graph enriched")

        # Extract the graph data via recall
        result = await cognee.recall(
            query_text="List all entities and their relationships",
            query_type=cognee.SearchType.GRAPH_COMPLETION,
        )

        return _parse_cognee_graph_result(result)

    except Exception:
        logger.exception("Cognee knowledge graph build failed")
        return CogneeGraphResponse()


def _parse_cognee_graph_result(result: object) -> CogneeGraphResponse:
    """Parse the raw Cognee recall result into structured entities and relationships."""
    entities: list[CogneeEntity] = []
    relationships: list[CogneeRelationship] = []

    if not result:
        return CogneeGraphResponse(entities=entities, relationships=relationships)

    # Cognee returns results in various formats depending on version
    # Handle list of dicts or string results
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                _extract_from_dict(item, entities, relationships)
    elif isinstance(result, dict):
        _extract_from_dict(result, entities, relationships)

    return CogneeGraphResponse(entities=entities, relationships=relationships)


def _extract_from_dict(
    data: dict,
    entities: list[CogneeEntity],
    relationships: list[CogneeRelationship],
) -> None:
    """Extract entities and relationships from a Cognee response dict."""
    # Handle nodes/edges format
    if "nodes" in data:
        for node in data.get("nodes", []):
            if isinstance(node, dict) and node.get("name"):
                entities.append(CogneeEntity(
                    name=str(node["name"]),
                    entity_type=_normalize_entity_type(str(node.get("type", "unknown"))),
                    properties={k: str(v) for k, v in node.items() if k not in ("name", "type")},
                ))

    if "edges" in data:
        for edge in data.get("edges", []):
            if isinstance(edge, dict) and edge.get("source") and edge.get("target"):
                relationships.append(CogneeRelationship(
                    source_entity=str(edge["source"]),
                    target_entity=str(edge["target"]),
                    relationship_type=str(edge.get("type", "related_to")),
                ))

    # Handle entities/relationships format
    if "entities" in data:
        for entity in data.get("entities", []):
            if isinstance(entity, dict) and entity.get("name"):
                entities.append(CogneeEntity(
                    name=str(entity["name"]),
                    entity_type=_normalize_entity_type(str(entity.get("type", "unknown"))),
                ))

    if "relationships" in data:
        for rel in data.get("relationships", []):
            if isinstance(rel, dict) and rel.get("source") and rel.get("target"):
                relationships.append(CogneeRelationship(
                    source_entity=str(rel["source"]),
                    target_entity=str(rel["target"]),
                    relationship_type=str(rel.get("type", "related_to")),
                ))


def _normalize_entity_type(raw_type: str) -> str:
    """Map Cognee entity labels to our internal type system."""
    return _ENTITY_TYPE_MAPPING.get(raw_type.lower(), raw_type.lower() or "unknown")


def merge_cognee_into_evidence_store(
    graph_response: CogneeGraphResponse,
    evidence_store: EvidenceStore,
    source_doc_id: str = "cognee",
) -> int:
    """Merge Cognee-discovered entities into the existing EvidenceStore.

    Handles deduplication: if an entity already exists, updates aliases.
    Returns the number of new entities added.
    """
    added = 0

    for cognee_entity in graph_response.entities:
        existing = evidence_store.get_entity(cognee_entity.name)
        if existing is not None:
            # Entity already exists — add source as alias if not present
            if source_doc_id not in existing.aliases:
                existing.aliases.append(f"cognee:{cognee_entity.entity_type}")
        else:
            evidence_store.add_entity(Entity(
                name=cognee_entity.name,
                entity_type=cognee_entity.entity_type,
                source_doc_id=source_doc_id,
                aliases=[],
            ))
            added += 1

    logger.info("Merged Cognee entities: %d new, %d existing", added, len(graph_response.entities) - added)
    return added


def merge_cognee_into_document_graph(
    graph_response: CogneeGraphResponse,
    document_graph: DocumentGraph,
    evidence_store: EvidenceStore,
) -> int:
    """Merge Cognee-discovered relationships into the existing DocumentGraph.

    For each relationship, finds which documents contain the source and target
    entities, and adds edges between those documents.
    Returns the number of new edges added.
    """
    added = 0

    for rel in graph_response.relationships:
        # Find documents containing the source entity
        source_docs = document_graph.get_documents_by_entity(rel.source_entity)
        target_docs = document_graph.get_documents_by_entity(rel.target_entity)

        # Create edges between documents that share related entities
        for src_doc in source_docs:
            entity = Entity(
                name=f"{rel.source_entity}->{rel.target_entity}",
                entity_type=rel.relationship_type,
                source_doc_id=src_doc,
            )
            for tgt_doc in target_docs:
                if src_doc != tgt_doc:
                    document_graph.add_entity_to_document(tgt_doc, entity)
                    added += 1

    logger.info("Merged Cognee relationships into graph: %d new edges", added)
    return added
