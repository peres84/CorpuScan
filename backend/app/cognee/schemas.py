from __future__ import annotations

from pydantic import BaseModel, Field


class CogneeEntity(BaseModel):
    """An entity discovered by Cognee's knowledge graph."""

    name: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    source_node_set: str = Field(default="")
    properties: dict[str, str] = Field(default_factory=dict)


class CogneeRelationship(BaseModel):
    """A relationship between two entities discovered by Cognee."""

    source_entity: str = Field(min_length=1)
    target_entity: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class CogneeGraphResponse(BaseModel):
    """Full graph response from Cognee containing entities and relationships."""

    entities: list[CogneeEntity] = Field(default_factory=list)
    relationships: list[CogneeRelationship] = Field(default_factory=list)
