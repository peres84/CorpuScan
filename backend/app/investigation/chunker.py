from __future__ import annotations

from app.investigation.models import ContentChunk, ParsedDocument

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP = 200


def chunk_document(
    document: ParsedDocument,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> ParsedDocument:
    """Split large document content into overlapping chunks with source references.

    If a document's chunks are already small enough (each under chunk_size chars),
    they are left as-is. Otherwise, individual chunks that exceed the limit are
    split into overlapping sub-chunks.
    """
    needs_rechunking = any(len(c.text) > chunk_size for c in document.content_chunks)
    if not needs_rechunking:
        return document

    new_chunks: list[ContentChunk] = []
    chunk_idx = 0

    for original in document.content_chunks:
        if len(original.text) <= chunk_size:
            new_chunks.append(
                ContentChunk(
                    text=original.text,
                    source_ref=original.source_ref,
                    chunk_index=chunk_idx,
                )
            )
            chunk_idx += 1
        else:
            sub_chunks = _split_text(original.text, chunk_size, overlap)
            for sub_idx, sub_text in enumerate(sub_chunks):
                new_chunks.append(
                    ContentChunk(
                        text=sub_text,
                        source_ref=f"{original.source_ref}:chunk:{sub_idx + 1}",
                        chunk_index=chunk_idx,
                    )
                )
                chunk_idx += 1

    return document.model_copy(update={"content_chunks": new_chunks})


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping segments, preferring line boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at a newline within the last 20% of the chunk
        boundary_search_start = end - chunk_size // 5
        newline_pos = text.rfind("\n", boundary_search_start, end)
        if newline_pos > start:
            end = newline_pos + 1

        chunks.append(text[start:end])
        start = end - overlap

    return chunks
