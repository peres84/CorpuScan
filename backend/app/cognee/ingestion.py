from __future__ import annotations

import logging

from app.cognee.client import CogneeClient
from app.investigation.models import DocumentType, ParsedDocument

logger = logging.getLogger(__name__)

# Map document types to Cognee node sets for organized retrieval
_NODE_SET_MAPPING: dict[DocumentType, str] = {
    DocumentType.TXT: "accounting_ledgers",
    DocumentType.CSV: "accounting_ledgers",
    DocumentType.XLSX: "financial_records",
    DocumentType.PDF: "reports",
    DocumentType.DOCX: "reports",
    DocumentType.XML: "metadata",
    DocumentType.UNKNOWN: "other",
}

# Batch size for Cognee ingestion to avoid overwhelming memory
_BATCH_SIZE = 5
_MAX_CONTENT_PER_DOC = 15000


def get_node_set(doc: ParsedDocument) -> str:
    """Determine the Cognee node set for a document based on its type and filename."""
    filename_lower = doc.filename.lower()

    # Override based on filename keywords
    if any(kw in filename_lower for kw in ("lieferant", "kredit", "vendor")):
        return "vendor_records"
    if any(kw in filename_lower for kw in ("wareneingang", "receipt", "goods")):
        return "receipts"
    if any(kw in filename_lower for kw in ("berechtigung", "permission", "user")):
        return "permissions"
    if any(kw in filename_lower for kw in ("buchung", "konto", "sachkonto", "journal")):
        return "accounting_ledgers"
    if any(kw in filename_lower for kw in ("saldo", "bilanz", "guv")):
        return "financial_records"
    if any(kw in filename_lower for kw in ("stammdaten", "master")):
        return "master_data"

    return _NODE_SET_MAPPING.get(doc.doc_type, "other")


def _build_ingestion_text(doc: ParsedDocument) -> str:
    """Convert ParsedDocument chunks into a single text block for Cognee ingestion."""
    parts: list[str] = []
    total_chars = 0

    # Prepend metadata header
    header = f"Document: {doc.filename}\nType: {doc.doc_type.value}\nID: {doc.doc_id}\n---\n"
    parts.append(header)
    total_chars += len(header)

    for chunk in doc.content_chunks:
        if total_chars + len(chunk.text) > _MAX_CONTENT_PER_DOC:
            remaining = _MAX_CONTENT_PER_DOC - total_chars
            if remaining > 100:
                parts.append(chunk.text[:remaining])
            break
        parts.append(chunk.text)
        total_chars += len(chunk.text)

    return "\n".join(parts)


async def ingest_documents(
    client: CogneeClient,
    documents: list[ParsedDocument],
) -> int:
    """Ingest parsed documents into Cognee's knowledge memory.

    Groups documents by node set and ingests in batches.
    Returns the number of documents successfully ingested.
    """
    if not client.is_available():
        logger.info("Cognee unavailable — skipping ingestion")
        return 0

    try:
        import cognee
    except ImportError:
        logger.warning("Cognee SDK not available for ingestion")
        return 0

    # Group documents by node set
    by_node_set: dict[str, list[ParsedDocument]] = {}
    for doc in documents:
        node_set = get_node_set(doc)
        by_node_set.setdefault(node_set, []).append(doc)

    ingested_count = 0

    for node_set, docs in by_node_set.items():
        # Process in batches
        for batch_start in range(0, len(docs), _BATCH_SIZE):
            batch = docs[batch_start:batch_start + _BATCH_SIZE]

            for doc in batch:
                text = _build_ingestion_text(doc)
                if not text.strip():
                    continue

                try:
                    await cognee.remember(
                        text,
                        node_set=[node_set],
                        self_improvement=False,
                    )
                    ingested_count += 1
                except Exception:
                    logger.warning("Cognee ingestion failed for %s — skipping", doc.filename)
                    continue

    logger.info("Cognee ingestion complete: %d/%d documents ingested", ingested_count, len(documents))
    return ingested_count
