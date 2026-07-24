from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.integrations.llm_router import LLMRouter
from app.integrations.openai import OpenAIClient
from app.integrations.tavily import TavilyClient
from app.investigation.agent import InvestigationAgent
from app.investigation.buffer import InvestigationState
from app.investigation.entities import extract_entities_from_document
from app.investigation.evidence_store import EvidenceStore, Finding
from app.investigation.graph import DocumentGraph
from app.investigation.models import DocumentType, ParsedDocument
from app.investigation.prioritization import select_start_documents
from app.investigation.structured import StructuredDataStore, extract_tabular, extract_unstructured

logger = logging.getLogger(__name__)


class InvestigationJobStep(StrEnum):
    PARSE = "parse"
    STRUCTURED_EXTRACT = "structured_extract"
    COGNEE_INGEST = "cognee_ingest"
    BUILD_GRAPH = "build_graph"
    INVESTIGATE = "investigate"
    REPORT = "report"
    DONE = "done"


class InvestigationJobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class InvestigationJobRecord:
    status: InvestigationJobState = InvestigationJobState.PENDING
    step: InvestigationJobStep = InvestigationJobStep.PARSE
    progress: int = 0
    error: str | None = None
    evidence_store: EvidenceStore = field(default_factory=EvidenceStore)
    structured_data_store: StructuredDataStore = field(default_factory=StructuredDataStore)
    graph: DocumentGraph = field(default_factory=DocumentGraph)
    investigation_state: InvestigationState | None = None
    findings: list[Finding] = field(default_factory=list)
    report: dict[str, object] | None = None


class InvestigationJobStore:
    """In-memory store for investigation jobs, following the same pattern as JobStore."""

    def __init__(self) -> None:
        self._jobs: dict[str, InvestigationJobRecord] = {}

    def create(self) -> str:
        job_id = str(uuid4())
        self._jobs[job_id] = InvestigationJobRecord()
        logger.info("Investigation job created: %s", job_id)
        return job_id

    def get(self, job_id: str) -> InvestigationJobRecord | None:
        return self._jobs.get(job_id)

    def update_step(self, job_id: str, *, step: InvestigationJobStep, progress: int) -> None:
        job = self._require(job_id)
        job.step = step
        job.progress = progress
        job.status = InvestigationJobState.RUNNING
        logger.info("Investigation [%s] step -> %s (%d%%)", job_id, step.value, progress)

    def set_error(self, job_id: str, message: str) -> None:
        job = self._require(job_id)
        job.status = InvestigationJobState.ERROR
        job.error = message
        logger.error("Investigation [%s] failed: %s", job_id, message)

    def set_done(self, job_id: str) -> None:
        job = self._require(job_id)
        job.status = InvestigationJobState.DONE
        job.step = InvestigationJobStep.DONE
        job.progress = 100
        logger.info("Investigation [%s] complete", job_id)

    def _require(self, job_id: str) -> InvestigationJobRecord:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown investigation job: {job_id}")
        return job


def _build_llm_router() -> LLMRouter:
    """Build an LLMRouter from settings. Gracefully handles missing keys."""
    settings = get_settings()

    openai_client: OpenAIClient | None = None
    gemini_client: GeminiClient | None = None

    if settings.openai_api_key and settings.openai_api_key.strip().lower() not in (
        "", "key_here", "your_api_key", "api_key_here", "replace_me",
    ):
        try:
            openai_client = OpenAIClient(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        except RuntimeError:
            pass

    if settings.gemini_api_key and settings.gemini_api_key.strip().lower() not in (
        "", "key_here", "your_api_key", "api_key_here", "replace_me",
    ):
        try:
            gemini_client = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
        except RuntimeError:
            pass

    return LLMRouter(openai_client=openai_client, gemini_client=gemini_client)


async def run_investigation_pipeline(
    job_store: InvestigationJobStore,
    job_id: str,
    documents: list[ParsedDocument],
    priority_doc_ids: list[str] | None = None,
) -> None:
    """Run the full investigation pipeline: parse → cognee → graph → investigate → report."""
    try:
        job = job_store.get(job_id)
        if job is None:
            return

        # Stage 1: Parse (documents already parsed if provided directly)
        job_store.update_step(job_id, step=InvestigationJobStep.PARSE, progress=10)
        for doc in documents:
            job.evidence_store.add_document(doc)
            job.graph.add_document(doc.doc_id, doc.filename)

        logger.info("Investigation [%s] parsed %d documents", job_id, len(documents))
        job_store.update_step(job_id, step=InvestigationJobStep.PARSE, progress=15)

        llm_router = _build_llm_router()

        job_store.update_step(job_id, step=InvestigationJobStep.STRUCTURED_EXTRACT, progress=16)
        for index, doc in enumerate(documents):
            if doc.doc_type in (DocumentType.CSV, DocumentType.XLSX, DocumentType.TXT):
                structured_file = extract_tabular(doc)
            else:
                structured_file = await extract_unstructured(doc, llm_router)
            job.structured_data_store.add_file(structured_file)
            progress = 16 + int((index + 1) / max(len(documents), 1) * 8)
            job_store.update_step(job_id, step=InvestigationJobStep.STRUCTURED_EXTRACT, progress=progress)
        job.structured_data_store.save_to_json(job_id)

        # Stage 2: Cognee ingestion (if enabled)
        cognee_client = await _try_cognee_ingest(
            job_store, job_id, documents, job.structured_data_store
        )

        # Stage 3: Build graph via entity extraction
        job_store.update_step(job_id, step=InvestigationJobStep.BUILD_GRAPH, progress=25)
        total_docs = len(documents)
        for idx, doc in enumerate(documents):
            entities = await extract_entities_from_document(doc, llm_router)
            for entity in entities:
                job.evidence_store.add_entity(entity)
                job.graph.add_entity_to_document(doc.doc_id, entity)
            progress = 25 + int((idx + 1) / total_docs * 25)
            job_store.update_step(job_id, step=InvestigationJobStep.BUILD_GRAPH, progress=progress)

        # Merge Cognee graph data if available
        if cognee_client is not None and cognee_client.is_available():
            await _merge_cognee_graph(cognee_client, job)

        logger.info(
            "Investigation [%s] graph built: %d nodes, %d edges, %d entities",
            job_id,
            job.graph.node_count,
            job.graph.edge_count,
            job.evidence_store.entity_count,
        )

        # Stage 4: Run investigation agent
        job_store.update_step(job_id, step=InvestigationJobStep.INVESTIGATE, progress=55)

        settings = get_settings()
        tavily_client: TavilyClient | None = None
        if settings.tavily_api_key and settings.tavily_api_key.strip().lower() not in (
            "", "key_here", "your_api_key",
        ):
            tavily_client = TavilyClient(api_key=settings.tavily_api_key)

        start_doc_ids = priority_doc_ids or select_start_documents(documents)

        agent = InvestigationAgent(
            llm_router=llm_router,
            evidence_store=job.evidence_store,
            graph=job.graph,
            structured_data_store=job.structured_data_store,
            tavily_client=tavily_client,
            cognee_client=cognee_client,
            max_iterations=min(len(documents), 50),
        )

        investigation_state = await agent.run(start_doc_ids=start_doc_ids)
        job.investigation_state = investigation_state

        job_store.update_step(job_id, step=InvestigationJobStep.INVESTIGATE, progress=85)
        logger.info(
            "Investigation [%s] agent done: %d docs visited, likelihood=%.2f",
            job_id,
            len(investigation_state.visited),
            investigation_state.overall_fraud_likelihood,
        )

        # Stage 5: Generate findings from investigation state
        job_store.update_step(job_id, step=InvestigationJobStep.REPORT, progress=90)
        findings = _extract_findings_from_state(investigation_state)
        job.findings = findings
        for finding in findings:
            job.evidence_store.add_finding(finding)

        job_store.set_done(job_id)

    except Exception as exc:
        logger.exception("Investigation [%s] pipeline failed: %s", job_id, exc)
        job_store.set_error(job_id, str(exc))


async def _try_cognee_ingest(
    job_store: InvestigationJobStore,
    job_id: str,
    documents: list[ParsedDocument],
    structured_data_store: StructuredDataStore,
) -> object | None:
    """Attempt Cognee ingestion. Returns CogneeClient if successful, None otherwise.

    If Cognee is disabled or fails, the pipeline continues without it.
    """
    settings = get_settings()
    if not settings.cognee_enabled:
        logger.info("Investigation [%s] Cognee disabled — skipping ingestion", job_id)
        return None

    try:
        from app.cognee.client import CogneeClient
        from app.cognee.ingestion import ingest_documents

        job_store.update_step(job_id, step=InvestigationJobStep.COGNEE_INGEST, progress=16)

        client = CogneeClient()
        initialized = await client.init()
        if not initialized:
            logger.info("Investigation [%s] Cognee not available — skipping", job_id)
            return None

        await client.reset()
        count = await ingest_documents(client, documents, structured_data_store)
        job_store.update_step(job_id, step=InvestigationJobStep.COGNEE_INGEST, progress=22)

        logger.info("Investigation [%s] Cognee ingested %d documents", job_id, count)
        return client

    except Exception:
        logger.warning("Investigation [%s] Cognee ingestion failed — continuing without it", job_id)
        return None


async def _merge_cognee_graph(cognee_client: object, job: InvestigationJobRecord) -> None:
    """Merge Cognee knowledge graph into the investigation graph."""
    try:
        from app.cognee.graph import (
            build_knowledge_graph,
            merge_cognee_into_document_graph,
            merge_cognee_into_evidence_store,
        )

        graph_response = await build_knowledge_graph(cognee_client)  # type: ignore[arg-type]
        merge_cognee_into_evidence_store(graph_response, job.evidence_store)
        merge_cognee_into_document_graph(graph_response, job.graph, job.evidence_store)
    except Exception:
        logger.warning("Cognee graph merge failed — continuing with existing graph")


def _extract_findings_from_state(state: InvestigationState) -> list[Finding]:
    """Extract findings from the investigation state based on high fraud likelihood docs."""
    findings: list[Finding] = []
    finding_counter = 0

    for row in state.buffer:
        if row.fraud_likelihood >= 0.4:
            finding_counter += 1
            findings.append(Finding(
                finding_id=f"finding_{finding_counter:03d}",
                finding_text=row.notes_summary,
                evidence=[],
                fraud_likelihood=row.fraud_likelihood,
            ))

    return findings
