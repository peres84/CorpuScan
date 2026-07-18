from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from app.integrations.llm_router import LLMRouter
from app.integrations.tavily import TavilyClient
from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import EvidenceStore
from app.investigation.graph import DocumentGraph
from app.investigation.models import ParsedDocument

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_MAX_CONTENT_FOR_LLM = 12000


def _load_investigator_prompt() -> dict[str, str]:
    path = _PROMPTS_DIR / "investigator.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class InvestigationAgent:
    """Autonomous LLM-driven investigator performing DFS over the document graph."""

    def __init__(
        self,
        *,
        llm_router: LLMRouter,
        evidence_store: EvidenceStore,
        graph: DocumentGraph,
        tavily_client: TavilyClient | None = None,
        max_iterations: int = 50,
    ) -> None:
        self._llm = llm_router
        self._store = evidence_store
        self._graph = graph
        self._tavily = tavily_client
        self._prompt_config = _load_investigator_prompt()
        self._state = InvestigationState(max_iterations=max_iterations)

    @property
    def state(self) -> InvestigationState:
        return self._state

    async def run(self, start_doc_ids: list[str]) -> InvestigationState:
        """Run the full DFS investigation loop starting from given documents."""
        # Initialize the stack with starting documents
        for doc_id in reversed(start_doc_ids):
            if doc_id not in self._state.stack:
                self._state.stack.append(doc_id)

        while not self._state.is_terminated():
            if not self._state.stack:
                break

            current_doc_id = self._state.stack.pop()

            if current_doc_id in self._state.visited:
                continue

            doc = self._store.get_document(current_doc_id)
            if doc is None:
                # Try to find by filename
                doc = self._find_document_by_filename(current_doc_id)
                if doc is None:
                    continue

            await self.investigate_document(doc)

        self._state.update_overall_likelihood()
        logger.info(
            "Investigation complete: %d documents visited, overall likelihood=%.2f",
            len(self._state.visited),
            self._state.overall_fraud_likelihood,
        )
        return self._state

    async def investigate_document(self, doc: ParsedDocument) -> InvestigationBufferRow:
        """Analyze a single document and update the investigation state."""
        self._state.add_visited(doc.doc_id)

        content = self._build_document_content(doc)
        related_docs = self._get_related_docs_summary(doc.doc_id)
        buffer_text = self._state.format_buffer_for_llm()

        system_prompt = self._prompt_config["system"]
        user_template = self._prompt_config["user_template"]
        user_prompt = user_template.format(
            investigation_buffer=buffer_text,
            filename=doc.filename,
            doc_id=doc.doc_id,
            doc_type=doc.doc_type.value,
            content=content,
            related_documents=related_docs,
        )

        try:
            response = await self._llm.generate(
                system=system_prompt,
                user=user_prompt,
                temperature=0.3,
                response_mime_type="application/json",
            )
            row = self._parse_agent_response(response, doc)
        except Exception:
            logger.exception("Agent failed on document %s", doc.filename)
            row = InvestigationBufferRow(
                doc_id=doc.doc_id,
                filename=doc.filename,
                notes_summary="Analysis failed due to LLM error.",
                fraud_likelihood=0.0,
            )

        self._state.buffer.append(row)
        self._update_stack_from_row(row)
        self._state.update_overall_likelihood()

        logger.info(
            "Investigated %s: likelihood=%.2f, next=%s, alts=%d",
            doc.filename,
            row.fraud_likelihood,
            row.primary_next_doc,
            len(row.alt_doc_leads),
        )
        return row

    def _build_document_content(self, doc: ParsedDocument) -> str:
        """Build content string from document chunks, limited for LLM context."""
        parts: list[str] = []
        total = 0
        for chunk in doc.content_chunks:
            if total + len(chunk.text) > _MAX_CONTENT_FOR_LLM:
                remaining = _MAX_CONTENT_FOR_LLM - total
                if remaining > 100:
                    parts.append(chunk.text[:remaining] + "\n[... truncated ...]")
                break
            parts.append(f"[{chunk.source_ref}]\n{chunk.text}")
            total += len(chunk.text)
        return "\n\n".join(parts) if parts else "(empty document)"

    def _get_related_docs_summary(self, doc_id: str) -> str:
        """Get a summary of related documents for context."""
        related_ids = self._graph.get_related_documents(doc_id)
        if not related_ids:
            return "No related documents found in graph."

        lines: list[str] = []
        for rel_id in related_ids[:10]:  # limit to 10 most related
            doc = self._store.get_document(rel_id)
            if doc:
                visited_mark = " (already visited)" if rel_id in self._state.visited else ""
                edges = self._graph.get_edges_between(doc_id, rel_id)
                shared = set(e.shared_entity for e in edges[:5])
                lines.append(
                    f"- {doc.filename}{visited_mark} (shared: {', '.join(shared) if shared else 'related'})"
                )
        return "\n".join(lines) if lines else "No related documents found."

    def _parse_agent_response(self, response: str, doc: ParsedDocument) -> InvestigationBufferRow:
        """Parse the LLM JSON response into an InvestigationBufferRow."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)

            return InvestigationBufferRow(
                doc_id=doc.doc_id,
                filename=doc.filename,
                notes_summary=str(data.get("notes_summary", ""))[:2000],
                fraud_likelihood=max(0.0, min(1.0, float(data.get("fraud_likelihood", 0.0)))),
                primary_next_doc=data.get("primary_next_doc") or None,
                alt_doc_leads=[str(d) for d in (data.get("alt_doc_leads") or []) if d],
                open_questions=[str(q) for q in (data.get("open_questions") or []) if q],
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("Failed to parse agent response for %s", doc.filename)
            return InvestigationBufferRow(
                doc_id=doc.doc_id,
                filename=doc.filename,
                notes_summary="Could not parse LLM response.",
                fraud_likelihood=0.0,
            )

    def _update_stack_from_row(self, row: InvestigationBufferRow) -> None:
        """Push new document leads onto the DFS stack."""
        # Alt leads go first (deeper in stack = explored later)
        for alt in reversed(row.alt_doc_leads):
            resolved_id = self._resolve_filename_to_id(alt)
            if resolved_id and resolved_id not in self._state.visited:
                if resolved_id not in self._state.stack:
                    self._state.stack.append(resolved_id)

        # Primary lead goes last (top of stack = explored next)
        if row.primary_next_doc:
            resolved_id = self._resolve_filename_to_id(row.primary_next_doc)
            if resolved_id and resolved_id not in self._state.visited:
                # Move to top of stack
                if resolved_id in self._state.stack:
                    self._state.stack.remove(resolved_id)
                self._state.stack.append(resolved_id)

    def _resolve_filename_to_id(self, filename: str) -> str | None:
        """Resolve a filename reference to a doc_id."""
        for doc in self._store.list_documents():
            if doc.filename == filename:
                return doc.doc_id
            if filename in doc.filename or doc.filename in filename:
                return doc.doc_id
        return None

    def _find_document_by_filename(self, name: str) -> ParsedDocument | None:
        """Find a document by filename or partial match."""
        for doc in self._store.list_documents():
            if doc.filename == name or name in doc.filename:
                return doc
        return None
