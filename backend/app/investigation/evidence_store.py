from __future__ import annotations

from pydantic import BaseModel, Field

from app.investigation.models import ParsedDocument


class EvidenceReference(BaseModel):
    doc_id: str = Field(min_length=1)
    location: str = Field(min_length=1)  # page number, row reference, or paragraph
    passage: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class Finding(BaseModel):
    finding_id: str = Field(min_length=1)
    finding_text: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    fraud_likelihood: float = Field(ge=0.0, le=1.0, default=0.0)


class Entity(BaseModel):
    name: str = Field(min_length=1)
    entity_type: str = Field(
        min_length=1
    )  # vendor, account, amount, date, invoice_number, person
    source_doc_id: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class EvidenceStore:
    """In-memory store for parsed documents, entities, and findings."""

    def __init__(self) -> None:
        self._documents: dict[str, ParsedDocument] = {}
        self._entities: dict[str, Entity] = {}  # keyed by entity name
        self._findings: dict[str, Finding] = {}  # keyed by finding_id

    def add_document(self, document: ParsedDocument) -> None:
        self._documents[document.doc_id] = document

    def get_document(self, doc_id: str) -> ParsedDocument | None:
        return self._documents.get(doc_id)

    def list_documents(self) -> list[ParsedDocument]:
        return list(self._documents.values())

    def remove_document(self, doc_id: str) -> bool:
        return self._documents.pop(doc_id, None) is not None

    def add_entity(self, entity: Entity) -> None:
        self._entities[entity.name] = entity

    def get_entity(self, name: str) -> Entity | None:
        return self._entities.get(name)

    def list_entities(self) -> list[Entity]:
        return list(self._entities.values())

    def get_entities_by_doc(self, doc_id: str) -> list[Entity]:
        return [e for e in self._entities.values() if e.source_doc_id == doc_id]

    def get_entities_by_type(self, entity_type: str) -> list[Entity]:
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def add_finding(self, finding: Finding) -> None:
        self._findings[finding.finding_id] = finding

    def get_finding(self, finding_id: str) -> Finding | None:
        return self._findings.get(finding_id)

    def list_findings(self) -> list[Finding]:
        return list(self._findings.values())

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def finding_count(self) -> int:
        return len(self._findings)
