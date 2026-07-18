from __future__ import annotations

import json
import logging

from app.integrations.llm_router import LLMRouter
from app.investigation.evidence_store import Entity
from app.investigation.models import ParsedDocument

logger = logging.getLogger(__name__)

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are a forensic accounting entity extractor. Given document content, extract all relevant entities.

Return a JSON array of objects, each with:
- "name": the entity value (e.g., "Ratio Consulting GmbH", "209101", "€48,000", "14.10.2025")
- "type": one of: "vendor", "account", "amount", "date", "invoice_number", "person", "company"
- "aliases": array of alternative names/references for this entity (can be empty)

Focus on:
- Vendor/company names and their account numbers
- Financial amounts (especially round amounts or near-threshold values)
- Account numbers (Sachkonto, Kreditor, Debitor numbers)
- Dates (booking dates, service dates, payment dates)
- Invoice/document reference numbers
- Person identifiers (user IDs like MV-U05)

Return ONLY the JSON array, no other text."""

# Limit content sent to LLM to avoid token limits
_MAX_CONTENT_CHARS = 8000


async def extract_entities_from_document(
    document: ParsedDocument,
    llm_router: LLMRouter,
) -> list[Entity]:
    """Extract entities from a document using the LLM."""
    content = _build_content_for_extraction(document)
    if not content.strip():
        return []

    try:
        response = await llm_router.generate(
            system=ENTITY_EXTRACTION_SYSTEM_PROMPT,
            user=f"Document: {document.filename}\n\nContent:\n{content}",
            temperature=0.1,
            response_mime_type="application/json",
        )
        return _parse_entity_response(response, document.doc_id)
    except Exception:
        logger.exception("Entity extraction failed for %s", document.filename)
        return []


def _build_content_for_extraction(document: ParsedDocument) -> str:
    """Build a content string from document chunks, limited to _MAX_CONTENT_CHARS."""
    parts: list[str] = []
    total_chars = 0
    for chunk in document.content_chunks:
        if total_chars + len(chunk.text) > _MAX_CONTENT_CHARS:
            remaining = _MAX_CONTENT_CHARS - total_chars
            if remaining > 100:
                parts.append(chunk.text[:remaining])
            break
        parts.append(chunk.text)
        total_chars += len(chunk.text)
    return "\n".join(parts)


def _parse_entity_response(response: str, doc_id: str) -> list[Entity]:
    """Parse the LLM JSON response into Entity objects."""
    try:
        # Strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)
        if not isinstance(data, list):
            return []

        entities: list[Entity] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            entity_type = str(item.get("type", "")).strip()
            aliases = item.get("aliases", [])
            if not name or not entity_type:
                continue
            if not isinstance(aliases, list):
                aliases = []
            entities.append(Entity(
                name=name,
                entity_type=entity_type,
                source_doc_id=doc_id,
                aliases=[str(a) for a in aliases if a],
            ))
        return entities
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse entity extraction response")
        return []
