from __future__ import annotations

import logging
from pathlib import Path

from app.investigation.chunker import chunk_document
from app.investigation.models import DocumentType, ParsedDocument
from app.investigation.parsers import detect_document_type, parse_document

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".xlsx", ".csv", ".docx", ".xml", ".md"}
SKIP_FILES = {"gdpdu-01-08-2002.dtd"}


def scan_directory(root: Path, chunk_size: int = 1500, overlap: int = 200) -> list[ParsedDocument]:
    """Recursively walk a directory and parse all supported files.

    Returns a list of ParsedDocument instances with content chunking applied.
    Files that fail to parse are logged and skipped.
    """
    documents: list[ParsedDocument] = []

    if not root.exists():
        logger.error("Directory does not exist: %s", root)
        return documents

    if not root.is_dir():
        logger.error("Path is not a directory: %s", root)
        return documents

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        if path.name in SKIP_FILES:
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.debug("Skipping unsupported file: %s", path)
            continue

        doc_type = detect_document_type(path)
        if doc_type == DocumentType.UNKNOWN:
            continue

        try:
            doc = parse_document(path)
            doc = chunk_document(doc, chunk_size=chunk_size, overlap=overlap)
            documents.append(doc)
            logger.info("Parsed %s (%d chunks)", path.name, len(doc.content_chunks))
        except Exception:
            logger.exception("Failed to parse %s — skipping", path)
            continue

    logger.info("Scan complete: %d documents parsed from %s", len(documents), root)
    return documents
