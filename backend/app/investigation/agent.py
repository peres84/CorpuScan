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
from app.investigation.structured import (
    StructuredDataStore,
    format_structured_file_summary,
)
from app.mcp.registry import get_tool

try:
    from app.cognee.client import CogneeClient
    from app.cognee.retrieval import search_context as cognee_search_context
except ImportError:
    CogneeClient = None  # type: ignore[assignment, misc]
    cognee_search_context = None  # type: ignore[assignment]

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
        structured_data_store: StructuredDataStore | None = None,
        tavily_client: TavilyClient | None = None,
        cognee_client: object | None = None,
        max_iterations: int = 50,
    ) -> None:
        self._llm = llm_router
        self._store = evidence_store
        self._graph = graph
        self._structured_data_store = structured_data_store
        self._tavily = tavily_client
        self._cognee = cognee_client
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
        structured_data_summary = self._build_structured_data_summary(doc.doc_id)
        related_docs = self._get_related_docs_summary(doc.doc_id)
        buffer_text = self._state.format_buffer_for_llm()

        # Query Cognee for additional context if available
        cognee_context = await self._get_cognee_context(doc)

        system_prompt = self._prompt_config["system"]
        user_template = self._prompt_config["user_template"]
        user_prompt = user_template.format(
            investigation_buffer=buffer_text,
            filename=doc.filename,
            doc_id=doc.doc_id,
            doc_type=doc.doc_type.value,
            content=content,
            structured_data_summary=structured_data_summary,
            related_documents=related_docs,
        )

        # Inject Cognee context if available
        if cognee_context:
            user_prompt += f"\n\n## Cognee Knowledge Context\n{cognee_context}"

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

        # Run Tavily queries if the agent requested any
        tavily_results = await self._run_tavily_queries(row)
        if tavily_results:
            row.tavily_results = tavily_results

        self._state.buffer.append(row)
        self._update_stack_from_row(row)
        self._state.update_overall_likelihood()

        logger.info(
            "Investigated %s: likelihood=%.2f, next=%s, alts=%d, flagged=%d, tavily=%d",
            doc.filename,
            row.fraud_likelihood,
            row.primary_next_doc,
            len(row.alt_doc_leads),
            len(row.flagged_entries),
            len(row.tavily_results),
        )
        return row

    async def _run_tavily_queries(
        self, row: InvestigationBufferRow
    ) -> list[dict[str, str]]:
        """Execute Tavily web searches requested by the agent."""
        # Check if the agent's response included tavily_queries (stored temporarily)
        queries = getattr(row, "_pending_tavily_queries", [])
        if not queries:
            return []

        results: list[dict[str, str]] = []
        for query in queries[:3]:  # Max 3 queries per document
            research = await self.research_via_mcp(query)
            if research:
                results.append({"query": query, "result": research})
                logger.info("Tavily research for %s: %s", row.filename, query)

        return results

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

    def _build_structured_data_summary(self, doc_id: str) -> str:
        if self._structured_data_store is None:
            return "No structured data available."
        structured_file = self._structured_data_store.get_file(doc_id)
        if structured_file is None:
            return "No structured data available."
        return format_structured_file_summary(structured_file)

    def _get_related_docs_summary(self, doc_id: str) -> str:
        """Get a summary of related documents for context."""
        related_ids = self._graph.get_related_documents(doc_id)
        if not related_ids:
            return "No related documents found in graph."

        lines: list[str] = []
        for rel_id in related_ids[:10]:  # limit to 10 most related
            doc = self._store.get_document(rel_id)
            if doc:
                visited_mark = (
                    " (already visited)" if rel_id in self._state.visited else ""
                )
                edges = self._graph.get_edges_between(doc_id, rel_id)
                shared = set(e.shared_entity for e in edges[:5])
                lines.append(
                    f"- {doc.filename}{visited_mark} (shared: {', '.join(shared) if shared else 'related'})"
                )
        return "\n".join(lines) if lines else "No related documents found."

    def _parse_agent_response(
        self, response: str, doc: ParsedDocument
    ) -> InvestigationBufferRow:
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

            # Parse flagged entries
            flagged_entries: list[dict[str, str]] = []
            for entry in data.get("flagged_entries") or []:
                if isinstance(entry, dict):
                    flagged_entries.append(
                        {
                            "row_ref": str(entry.get("row_ref", "")),
                            "data": str(entry.get("data", "")),
                            "reason": str(entry.get("reason", "")),
                        }
                    )

            # Parse related files
            related_files: list[dict[str, str]] = []
            for rf in data.get("related_files") or []:
                if isinstance(rf, dict) and rf.get("filename"):
                    related_files.append(
                        {
                            "filename": str(rf.get("filename", "")),
                            "relationship": str(rf.get("relationship", "")),
                            "suspicion_contribution": str(
                                rf.get("suspicion_contribution", "")
                            ),
                        }
                    )

            row = InvestigationBufferRow(
                doc_id=doc.doc_id,
                filename=doc.filename,
                notes_summary=str(data.get("notes_summary", ""))[:2000],
                fraud_likelihood=max(
                    0.0, min(1.0, float(data.get("fraud_likelihood", 0.0)))
                ),
                primary_next_doc=data.get("primary_next_doc") or None,
                alt_doc_leads=[str(d) for d in (data.get("alt_doc_leads") or []) if d],
                open_questions=[
                    str(q) for q in (data.get("open_questions") or []) if q
                ],
                flagged_entries=flagged_entries,
                related_files=related_files,
            )

            # Stash tavily queries for execution after parsing
            tavily_queries = [str(q) for q in (data.get("tavily_queries") or []) if q]
            row._pending_tavily_queries = tavily_queries  # type: ignore[attr-defined]

            return row
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("Failed to parse agent response for %s", doc.filename)
            return InvestigationBufferRow(
                doc_id=doc.doc_id,
                filename=doc.filename,
                notes_summary="Could not parse LLM response.",
                fraud_likelihood=0.0,
            )

    def _update_stack_from_row(self, row: InvestigationBufferRow) -> None:
        """Push new document leads onto the DFS stack.

        Combines LLM-suggested leads with Cognee relationship graph suggestions.
        Cognee leads that have strong entity connections are prioritized.
        Leads with no entity overlap to the current doc are deprioritized.
        """
        all_leads = self._get_investigation_leads(row)

        # Push deprioritized leads first (bottom of stack)
        for lead_id in reversed(all_leads["deprioritized"]):
            if lead_id not in self._state.visited and lead_id not in self._state.stack:
                self._state.stack.append(lead_id)

        # Alt leads next
        for alt in reversed(row.alt_doc_leads):
            resolved_id = self._resolve_filename_to_id(alt)
            if resolved_id and resolved_id not in self._state.visited:
                if resolved_id not in self._state.stack:
                    self._state.stack.append(resolved_id)

        # Cognee-suggested leads (strong entity connections)
        for lead_id in reversed(all_leads["cognee_suggested"]):
            if lead_id not in self._state.visited and lead_id not in self._state.stack:
                self._state.stack.append(lead_id)

        # Primary lead goes last (top of stack = explored next)
        if row.primary_next_doc:
            resolved_id = self._resolve_filename_to_id(row.primary_next_doc)
            if resolved_id and resolved_id not in self._state.visited:
                if resolved_id in self._state.stack:
                    self._state.stack.remove(resolved_id)
                self._state.stack.append(resolved_id)

    def _get_investigation_leads(
        self, row: InvestigationBufferRow
    ) -> dict[str, list[str]]:
        """Combine LLM-suggested next docs with Cognee relationship graph suggestions.

        Returns dict with:
        - 'cognee_suggested': doc_ids with strong entity connections (from graph)
        - 'deprioritized': doc_ids with no entity overlap (less likely relevant)
        """
        result: dict[str, list[str]] = {"cognee_suggested": [], "deprioritized": []}

        # Get graph-related documents for the current doc
        related_ids = self._graph.get_related_documents(row.doc_id)

        # Get the current document's entities for overlap checking
        current_node = self._graph.get_node(row.doc_id)
        current_entities = current_node.entity_names if current_node else set()

        for rel_id in related_ids:
            if rel_id in self._state.visited:
                continue

            rel_node = self._graph.get_node(rel_id)
            if rel_node is None:
                continue

            # Check entity overlap
            overlap = current_entities & rel_node.entity_names
            if len(overlap) >= 2:
                # Strong connection — suggest via Cognee path
                result["cognee_suggested"].append(rel_id)
            elif len(overlap) == 0:
                # No overlap — deprioritize
                result["deprioritized"].append(rel_id)

        return result

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

    async def _get_cognee_context(self, doc: ParsedDocument) -> str:
        """Query Cognee for context related to the current document.

        Returns formatted context string, or empty string if Cognee is unavailable.
        """
        if self._cognee is None or cognee_search_context is None:
            return ""

        if not hasattr(self._cognee, "is_available") or not self._cognee.is_available():
            return ""

        try:
            # Build a query from the document's key content
            query = f"Relationships and entities in {doc.filename}"
            context = await cognee_search_context(self._cognee, query)
            return context if context else ""
        except Exception:
            logger.debug("Cognee context retrieval failed for %s", doc.filename)
            return ""

    async def research_via_mcp(self, query: str) -> str | None:
        """Use the MCP web.search tool for external research, falling back to direct HTTP.

        Tries the internal MCP registry first. If that fails (tool not registered,
        Tavily key missing, network error), falls back to the TavilyClient passed
        at construction time.

        Returns search results as formatted text, or None if both paths fail.
        """
        # Try MCP first
        tool = get_tool("web.search")
        if tool is not None:
            try:
                result = tool.handler(query=query, max_results=3)
                items = result.get("results", [])
                if items:
                    lines = [f"External research for: {query}"]
                    for item in items:
                        lines.append(
                            f"- {item.get('title', '')}: {item.get('snippet', '')}"
                        )
                    return "\n".join(lines)
            except Exception:
                logger.debug(
                    "MCP web.search failed for query: %s — falling back to HTTP", query
                )

        # Fallback to direct TavilyClient
        if self._tavily is not None:
            try:
                results = await self._tavily.search(query, max_results=3)
                if results:
                    lines = [f"External research for: {query}"]
                    for item in results:
                        lines.append(f"- {item.title}: {item.content or ''}")
                    return "\n".join(lines)
            except Exception:
                logger.debug("Tavily HTTP fallback also failed for query: %s", query)

        return None
