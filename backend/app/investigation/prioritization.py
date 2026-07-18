from __future__ import annotations

from app.investigation.models import DocumentType, ParsedDocument

# Document type weights — higher = more likely to be investigatively relevant
_TYPE_WEIGHTS: dict[DocumentType, float] = {
    DocumentType.CSV: 0.7,
    DocumentType.XLSX: 0.7,
    DocumentType.TXT: 0.6,
    DocumentType.PDF: 0.5,
    DocumentType.DOCX: 0.4,
    DocumentType.XML: 0.3,
    DocumentType.UNKNOWN: 0.1,
}

# Filename keywords that suggest high investigative relevance
_HIGH_PRIORITY_KEYWORDS = [
    "buchung", "lieferant", "kredit", "zahlung", "rechnung", "invoice",
    "payment", "vendor", "bank", "konto", "saldo", "saldenliste",
    "wareneingangsliste", "wareneingang", "faktura", "journal",
    "berechtigung", "stammdaten", "pruefung", "prüfung",
]

# Filename keywords that suggest lower priority (metadata, schema files)
_LOW_PRIORITY_KEYWORDS = [
    "index", "gdpdu", "dtd", "export", "protokoll", "it-bestaetigung",
    "vollstaendigkeit",
]

# Financial-relevance keywords in content
_FINANCIAL_KEYWORDS = [
    "eur", "€", "betrag", "summe", "zahlung", "rechnung", "kredit",
    "debit", "saldo", "konto", "buchung", "invoice", "payment", "amount",
]


def compute_priority_score(document: ParsedDocument) -> float:
    """Compute a priority score (0.0 to 1.0) for a document.

    Higher scores indicate documents more likely to be relevant for
    fraud investigation. Considers:
    - Document type weight
    - Filename keyword matches
    - Content financial relevance
    """
    score = 0.0

    # Type weight (0-0.3)
    type_weight = _TYPE_WEIGHTS.get(document.doc_type, 0.1)
    score += type_weight * 0.3

    # Filename relevance (0-0.4)
    filename_lower = document.filename.lower()
    high_matches = sum(1 for kw in _HIGH_PRIORITY_KEYWORDS if kw in filename_lower)
    low_matches = sum(1 for kw in _LOW_PRIORITY_KEYWORDS if kw in filename_lower)

    if high_matches > 0:
        score += min(0.4, high_matches * 0.15)
    if low_matches > 0:
        score -= min(0.2, low_matches * 0.1)

    # Content financial relevance (0-0.3)
    content_sample = " ".join(
        chunk.text[:500] for chunk in document.content_chunks[:5]
    ).lower()

    if content_sample:
        financial_matches = sum(1 for kw in _FINANCIAL_KEYWORDS if kw in content_sample)
        score += min(0.3, financial_matches * 0.05)

    return max(0.0, min(1.0, score))


def rank_documents_by_priority(documents: list[ParsedDocument]) -> list[ParsedDocument]:
    """Sort documents by priority score, highest first."""
    scored = [(doc, compute_priority_score(doc)) for doc in documents]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored]


def select_start_documents(
    documents: list[ParsedDocument],
    max_start_docs: int = 5,
) -> list[str]:
    """Select the best starting documents for investigation when user doesn't specify.

    Returns doc_ids of the top-priority documents.
    """
    ranked = rank_documents_by_priority(documents)
    return [doc.doc_id for doc in ranked[:max_start_docs]]
