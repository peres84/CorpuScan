from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.integrations.llm_router import LLMRouter
from app.investigation.buffer import InvestigationState
from app.investigation.evidence_store import Entity, EvidenceStore, Finding

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class TimelineEvent(BaseModel):
    date: str = Field(min_length=1)
    event: str = Field(min_length=1)
    source: str = Field(default="")


class EntityRelationship(BaseModel):
    entity_a: str = Field(min_length=1)
    entity_b: str = Field(min_length=1)
    relationship: str = Field(min_length=1)


class FraudAssessment(BaseModel):
    overall_likelihood: float = Field(ge=0.0, le=1.0)
    estimated_financial_impact: str = Field(default="Unknown")
    schemes_identified: list[str] = Field(default_factory=list)


class ReportFinding(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: str = Field(default="medium")
    fraud_likelihood: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence_references: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    executive_summary: str = Field(default="")
    findings: list[ReportFinding] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    entity_relationships: list[EntityRelationship] = Field(default_factory=list)
    fraud_assessment: FraudAssessment = Field(default_factory=lambda: FraudAssessment(overall_likelihood=0.0))
    remaining_questions: list[str] = Field(default_factory=list)
    relationship_chains: list[str] = Field(default_factory=list)
    knowledge_graph_summary: str = Field(default="")


def _load_report_prompt() -> dict[str, str]:
    path = _PROMPTS_DIR / "report_generator.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ReportGenerator:
    """Generates a structured investigation report from completed investigation state."""

    def __init__(self, llm_router: LLMRouter) -> None:
        self._llm = llm_router
        self._prompt_config = _load_report_prompt()

    async def generate(
        self,
        state: InvestigationState,
        evidence_store: EvidenceStore,
        cognee_graph: object | None = None,
    ) -> InvestigationReport:
        """Generate a full report from investigation state and evidence store.

        If cognee_graph (a CogneeGraphResponse) is provided, relationship chains
        and a knowledge graph summary are included in the report.
        """
        # Build context for the LLM
        buffer_text = state.format_buffer_for_llm()
        findings_text = self._format_findings(evidence_store.list_findings())
        entities_text = self._format_entities(evidence_store.list_entities())

        user_template = self._prompt_config["user_template"]
        user_prompt = user_template.format(
            investigation_buffer=buffer_text,
            findings_summary=findings_text,
            entities_summary=entities_text,
        )

        try:
            response = await self._llm.generate(
                system=self._prompt_config["system"],
                user=user_prompt,
                temperature=0.2,
                response_mime_type="application/json",
            )
            report = self._parse_report_response(response, state)
        except Exception:
            logger.exception("Report generation failed, producing fallback report")
            report = self._build_fallback_report(state, evidence_store)

        # Enrich with Cognee data if available
        if cognee_graph is not None:
            report = self._enrich_with_cognee(report, cognee_graph, evidence_store)

        return report

    def _enrich_with_cognee(
        self,
        report: InvestigationReport,
        cognee_graph: object,
        evidence_store: EvidenceStore,
    ) -> InvestigationReport:
        """Add Cognee relationship chains and knowledge graph summary to report."""
        try:
            from app.cognee.schemas import CogneeGraphResponse

            if not isinstance(cognee_graph, CogneeGraphResponse):
                return report

            # Build relationship chains (e.g., "MV-U05 → created → Vendor 209101 → invoiced → €248,000")
            chains = build_relationship_chains(cognee_graph)
            if chains:
                report.relationship_chains = chains

            # Build knowledge graph summary
            summary = build_knowledge_graph_summary(cognee_graph)
            if summary:
                report.knowledge_graph_summary = summary

        except Exception:
            logger.debug("Failed to enrich report with Cognee data")

        return report

    def _format_findings(self, findings: list[Finding]) -> str:
        if not findings:
            return "No findings recorded."
        lines: list[str] = []
        for f in findings:
            lines.append(f"- [{f.finding_id}] (likelihood={f.fraud_likelihood:.2f}): {f.finding_text}")
        return "\n".join(lines)

    def _format_entities(self, entities: list[Entity]) -> str:
        if not entities:
            return "No entities extracted."
        # Group by type
        by_type: dict[str, list[str]] = {}
        for e in entities:
            by_type.setdefault(e.entity_type, []).append(e.name)
        lines: list[str] = []
        for etype, names in sorted(by_type.items()):
            lines.append(f"  {etype}: {', '.join(names[:20])}")
        return "\n".join(lines)

    def _parse_report_response(self, response: str, state: InvestigationState) -> InvestigationReport:
        """Parse LLM JSON response into an InvestigationReport."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:])
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)

            findings = [
                ReportFinding(
                    title=str(f.get("title", "Finding")),
                    description=str(f.get("description", "")),
                    severity=str(f.get("severity", "medium")),
                    fraud_likelihood=max(0.0, min(1.0, float(f.get("fraud_likelihood", 0.0)))),
                    evidence_references=[str(r) for r in (f.get("evidence_references") or [])],
                )
                for f in (data.get("findings") or [])
                if isinstance(f, dict)
            ]

            timeline = [
                TimelineEvent(
                    date=str(t.get("date", "unknown")),
                    event=str(t.get("event", "")),
                    source=str(t.get("source", "")),
                )
                for t in (data.get("timeline") or [])
                if isinstance(t, dict) and t.get("event")
            ]

            entity_rels = [
                EntityRelationship(
                    entity_a=str(r.get("entity_a", "")),
                    entity_b=str(r.get("entity_b", "")),
                    relationship=str(r.get("relationship", "")),
                )
                for r in (data.get("entity_relationships") or [])
                if isinstance(r, dict) and r.get("entity_a") and r.get("entity_b")
            ]

            fraud_data = data.get("fraud_assessment") or {}
            fraud_assessment = FraudAssessment(
                overall_likelihood=max(0.0, min(1.0, float(fraud_data.get("overall_likelihood", state.overall_fraud_likelihood)))),
                estimated_financial_impact=str(fraud_data.get("estimated_financial_impact", "Unknown")),
                schemes_identified=[str(s) for s in (fraud_data.get("schemes_identified") or [])],
            )

            return InvestigationReport(
                executive_summary=str(data.get("executive_summary", "")),
                findings=findings,
                timeline=timeline,
                entity_relationships=entity_rels,
                fraud_assessment=fraud_assessment,
                remaining_questions=[str(q) for q in (data.get("remaining_questions") or []) if q],
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("Failed to parse report response")
            return self._build_fallback_report(state, EvidenceStore())

    def _build_fallback_report(
        self, state: InvestigationState, evidence_store: EvidenceStore
    ) -> InvestigationReport:
        """Build a basic report from investigation state without LLM."""
        findings = [
            ReportFinding(
                title=f"Suspicious activity in {row.filename}",
                description=row.notes_summary,
                severity="high" if row.fraud_likelihood >= 0.7 else "medium",
                fraud_likelihood=row.fraud_likelihood,
            )
            for row in state.buffer
            if row.fraud_likelihood >= 0.4
        ]

        timeline = reconstruct_timeline(state)
        entity_rels = extract_entity_relationships(evidence_store)

        return InvestigationReport(
            executive_summary=f"Investigation analyzed {len(state.visited)} documents. "
            f"Overall fraud likelihood: {state.overall_fraud_likelihood:.0%}.",
            findings=findings,
            timeline=timeline,
            entity_relationships=entity_rels,
            fraud_assessment=FraudAssessment(
                overall_likelihood=state.overall_fraud_likelihood,
                estimated_financial_impact="Requires further analysis",
                schemes_identified=[],
            ),
            remaining_questions=[q for row in state.buffer for q in row.open_questions],
        )


def reconstruct_timeline(state: InvestigationState) -> list[TimelineEvent]:
    """Reconstruct a chronological timeline from investigation buffer."""
    events: list[TimelineEvent] = []
    for idx, row in enumerate(state.buffer, start=1):
        events.append(TimelineEvent(
            date=f"Step {idx}",
            event=row.notes_summary[:200] if row.notes_summary else f"Analyzed {row.filename}",
            source=row.filename,
        ))
    return events


def extract_entity_relationships(evidence_store: EvidenceStore) -> list[EntityRelationship]:
    """Extract entity relationships from the evidence store."""
    entities = evidence_store.list_entities()
    if not entities:
        return []

    # Group entities by document — entities in the same doc are related
    by_doc: dict[str, list[Entity]] = {}
    for entity in entities:
        by_doc.setdefault(entity.source_doc_id, []).append(entity)

    relationships: list[EntityRelationship] = []
    seen: set[tuple[str, str]] = set()

    for doc_entities in by_doc.values():
        vendors = [e for e in doc_entities if e.entity_type == "vendor"]
        amounts = [e for e in doc_entities if e.entity_type == "amount"]
        accounts = [e for e in doc_entities if e.entity_type == "account"]

        # Link vendors to amounts in the same document
        for vendor in vendors[:5]:
            for amount in amounts[:5]:
                key = (vendor.name, amount.name)
                if key not in seen:
                    seen.add(key)
                    relationships.append(EntityRelationship(
                        entity_a=vendor.name,
                        entity_b=amount.name,
                        relationship="payment/invoice",
                    ))

        # Link vendors to accounts
        for vendor in vendors[:5]:
            for account in accounts[:5]:
                key = (vendor.name, account.name)
                if key not in seen:
                    seen.add(key)
                    relationships.append(EntityRelationship(
                        entity_a=vendor.name,
                        entity_b=account.name,
                        relationship="posted to account",
                    ))

    return relationships[:50]  # Cap at 50 relationships


def aggregate_fraud_assessment(state: InvestigationState) -> FraudAssessment:
    """Combine per-document likelihoods into overall score."""
    if not state.buffer:
        return FraudAssessment(overall_likelihood=0.0)

    max_likelihood = max(row.fraud_likelihood for row in state.buffer)
    avg_likelihood = sum(row.fraud_likelihood for row in state.buffer) / len(state.buffer)

    # Use weighted combination: 70% max, 30% average
    overall = 0.7 * max_likelihood + 0.3 * avg_likelihood

    return FraudAssessment(
        overall_likelihood=min(1.0, overall),
        estimated_financial_impact="Requires detailed analysis",
        schemes_identified=[],
    )


def build_relationship_chains(cognee_graph: object) -> list[str]:
    """Build human-readable relationship chains from Cognee graph data.

    Example: "MV-U05 → created → Vendor 209101 → invoiced → €248,000"
    """
    from app.cognee.schemas import CogneeGraphResponse

    if not isinstance(cognee_graph, CogneeGraphResponse):
        return []

    if not cognee_graph.relationships:
        return []

    # Build adjacency list from relationships
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for rel in cognee_graph.relationships:
        adjacency.setdefault(rel.source_entity, []).append(
            (rel.relationship_type, rel.target_entity)
        )

    # Build chains (max depth 4, starting from each entity)
    chains: list[str] = []
    seen_chains: set[str] = set()

    for start_entity in list(adjacency.keys())[:20]:
        chain = _build_chain(start_entity, adjacency, max_depth=4)
        if chain and chain not in seen_chains:
            seen_chains.add(chain)
            chains.append(chain)

    return chains[:15]  # Cap at 15 chains


def _build_chain(start: str, adjacency: dict[str, list[tuple[str, str]]], max_depth: int) -> str:
    """Build a single chain string from a starting entity."""
    parts = [start]
    current = start
    visited: set[str] = {start}

    for _ in range(max_depth):
        neighbors = adjacency.get(current, [])
        if not neighbors:
            break
        # Pick first unvisited neighbor
        next_hop = None
        for rel_type, target in neighbors:
            if target not in visited:
                parts.append(rel_type)
                parts.append(target)
                visited.add(target)
                next_hop = target
                break
        if next_hop is None:
            break
        current = next_hop

    if len(parts) < 3:
        return ""
    return " → ".join(parts)


def build_knowledge_graph_summary(cognee_graph: object) -> str:
    """Build a text summary of the Cognee knowledge graph."""
    from app.cognee.schemas import CogneeGraphResponse

    if not isinstance(cognee_graph, CogneeGraphResponse):
        return ""

    entity_count = len(cognee_graph.entities)
    rel_count = len(cognee_graph.relationships)

    if entity_count == 0:
        return ""

    # Count by type
    type_counts: dict[str, int] = {}
    for entity in cognee_graph.entities:
        type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1

    type_summary = ", ".join(f"{count} {etype}(s)" for etype, count in sorted(type_counts.items()))

    return (
        f"Knowledge graph contains {entity_count} entities and {rel_count} relationships. "
        f"Entity breakdown: {type_summary}."
    )
