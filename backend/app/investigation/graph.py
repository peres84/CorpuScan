from __future__ import annotations

from dataclasses import dataclass, field

from app.investigation.evidence_store import Entity


@dataclass
class GraphEdge:
    """An edge between two documents, representing a shared entity."""

    source_doc_id: str
    target_doc_id: str
    shared_entity: str
    entity_type: str


@dataclass
class DocumentNode:
    """A node in the document graph."""

    doc_id: str
    filename: str
    entity_names: set[str] = field(default_factory=set)


class DocumentGraph:
    """In-memory document relationship graph.

    Nodes are documents. Edges connect documents that share entities
    (vendors, account numbers, invoice numbers, etc.).
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DocumentNode] = {}
        self._edges: list[GraphEdge] = []
        # entity_name -> set of doc_ids containing that entity
        self._entity_index: dict[str, set[str]] = {}

    def add_document(self, doc_id: str, filename: str) -> None:
        if doc_id not in self._nodes:
            self._nodes[doc_id] = DocumentNode(doc_id=doc_id, filename=filename)

    def add_entity_to_document(self, doc_id: str, entity: Entity) -> None:
        """Register an entity as belonging to a document and build edges."""
        node = self._nodes.get(doc_id)
        if node is None:
            return

        entity_key = entity.name.lower().strip()
        node.entity_names.add(entity_key)

        # Update entity index
        if entity_key not in self._entity_index:
            self._entity_index[entity_key] = set()

        # Build edges to other documents that share this entity
        existing_docs = self._entity_index[entity_key]
        for other_doc_id in existing_docs:
            if other_doc_id != doc_id:
                self._edges.append(GraphEdge(
                    source_doc_id=doc_id,
                    target_doc_id=other_doc_id,
                    shared_entity=entity.name,
                    entity_type=entity.entity_type,
                ))

        self._entity_index[entity_key].add(doc_id)

        # Also index aliases
        for alias in entity.aliases:
            alias_key = alias.lower().strip()
            if not alias_key:
                continue
            if alias_key not in self._entity_index:
                self._entity_index[alias_key] = set()
            for other_doc_id in self._entity_index[alias_key]:
                if other_doc_id != doc_id:
                    self._edges.append(GraphEdge(
                        source_doc_id=doc_id,
                        target_doc_id=other_doc_id,
                        shared_entity=alias,
                        entity_type=entity.entity_type,
                    ))
            self._entity_index[alias_key].add(doc_id)

    def get_related_documents(self, doc_id: str) -> list[str]:
        """Get all document IDs connected to the given document."""
        related: set[str] = set()
        for edge in self._edges:
            if edge.source_doc_id == doc_id:
                related.add(edge.target_doc_id)
            elif edge.target_doc_id == doc_id:
                related.add(edge.source_doc_id)
        return sorted(related)

    def get_documents_by_entity(self, entity_name: str) -> list[str]:
        """Get all document IDs that contain the given entity."""
        key = entity_name.lower().strip()
        return sorted(self._entity_index.get(key, set()))

    def get_edges_between(self, doc_id_a: str, doc_id_b: str) -> list[GraphEdge]:
        """Get all edges connecting two specific documents."""
        return [
            e for e in self._edges
            if (e.source_doc_id == doc_id_a and e.target_doc_id == doc_id_b)
            or (e.source_doc_id == doc_id_b and e.target_doc_id == doc_id_a)
        ]

    def get_shared_entities(self, doc_id_a: str, doc_id_b: str) -> list[str]:
        """Get entity names shared between two documents."""
        node_a = self._nodes.get(doc_id_a)
        node_b = self._nodes.get(doc_id_b)
        if node_a is None or node_b is None:
            return []
        return sorted(node_a.entity_names & node_b.entity_names)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_node(self, doc_id: str) -> DocumentNode | None:
        return self._nodes.get(doc_id)
