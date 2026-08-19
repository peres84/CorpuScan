from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import Entity, EvidenceStore, Finding
from app.investigation.report import (
    InvestigationReport,
    ReportGenerator,
    aggregate_fraud_assessment,
    extract_entity_relationships,
    reconstruct_timeline,
)


def _build_completed_state() -> InvestigationState:
    """Build a realistic completed investigation state."""
    return InvestigationState(
        buffer=[
            InvestigationBufferRow(
                doc_id="d1",
                filename="Lieferantenbuchungen.txt",
                notes_summary="Found 5 round-amount invoices to Ratio Consulting GmbH (209101). "
                "All amounts are exactly €50,000, €48,000, €50,000, €50,000, €50,000. "
                "No goods receipt found for any of these invoices.",
                fraud_likelihood=0.85,
                primary_next_doc="Stammdatenaenderungen_2025.csv",
                alt_doc_leads=["Wareneingangsliste_2025.csv"],
                open_questions=["Who created vendor 209101?"],
            ),
            InvestigationBufferRow(
                doc_id="d2",
                filename="Stammdatenaenderungen_2025.csv",
                notes_summary="Vendor 209101 (Ratio Consulting GmbH) was created by MV-U05 "
                "and approved by MV-U05 — same user. Segregation of duties violated.",
                fraud_likelihood=0.92,
                primary_next_doc="Berechtigungsauswertung_2025.xlsx",
                alt_doc_leads=[],
                open_questions=[],
            ),
            InvestigationBufferRow(
                doc_id="d3",
                filename="Berechtigungsauswertung_2025.xlsx",
                notes_summary="MV-U05 has permissions: Buchen, Zahlungslauf, Kreditor anlegen. "
                "This user can create vendors, post invoices, and run payment runs alone.",
                fraud_likelihood=0.90,
                primary_next_doc=None,
                alt_doc_leads=[],
                open_questions=[],
            ),
        ],
        visited={"d1", "d2", "d3"},
        overall_fraud_likelihood=0.92,
        iteration_count=3,
    )


def _build_evidence_store() -> EvidenceStore:
    store = EvidenceStore()
    store.add_entity(
        Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="d1")
    )
    store.add_entity(Entity(name="209101", entity_type="account", source_doc_id="d1"))
    store.add_entity(Entity(name="€248,000", entity_type="amount", source_doc_id="d1"))
    store.add_entity(Entity(name="MV-U05", entity_type="person", source_doc_id="d2"))
    store.add_finding(
        Finding(
            finding_id="f001",
            finding_text="Fake vendor scheme detected",
            fraud_likelihood=0.92,
        )
    )
    return store


class FakeLLMForReport:
    async def generate(self, **kwargs: object) -> str:
        return json.dumps(
            {
                "executive_summary": "Investigation found strong evidence of a fake vendor scheme.",
                "findings": [
                    {
                        "title": "Fake Vendor — Ratio Consulting GmbH",
                        "description": "Shell vendor 209101 received €248,000 in round-amount invoices.",
                        "severity": "critical",
                        "fraud_likelihood": 0.92,
                        "evidence_references": [
                            "Lieferantenbuchungen.txt:row:45 — €50,000 Beratung invoice",
                            "Stammdatenaenderungen_2025.csv:row:7 — creator=approver=MV-U05",
                        ],
                    }
                ],
                "timeline": [
                    {
                        "date": "2025-05-12",
                        "event": "Vendor 209101 created by MV-U05",
                        "source": "Stammdatenaenderungen",
                    },
                    {
                        "date": "2025-06-01",
                        "event": "First invoice €50,000",
                        "source": "Lieferantenbuchungen",
                    },
                ],
                "entity_relationships": [
                    {
                        "entity_a": "MV-U05",
                        "entity_b": "Ratio Consulting GmbH",
                        "relationship": "created and paid",
                    },
                    {
                        "entity_a": "Ratio Consulting GmbH",
                        "entity_b": "209101",
                        "relationship": "vendor account",
                    },
                ],
                "fraud_assessment": {
                    "overall_likelihood": 0.92,
                    "estimated_financial_impact": "€248,000 cash misappropriation",
                    "schemes_identified": ["Fake vendor / shell company scheme"],
                },
                "remaining_questions": ["Are there co-conspirators beyond MV-U05?"],
            }
        )


class TestReportGenerator:
    @pytest.mark.asyncio
    async def test_generates_complete_report(self) -> None:
        """Given a completed investigation state, verify report structure is complete."""
        state = _build_completed_state()
        store = _build_evidence_store()
        generator = ReportGenerator(llm_router=FakeLLMForReport())  # type: ignore[arg-type]

        report = await generator.generate(state, store)

        assert isinstance(report, InvestigationReport)
        assert report.executive_summary != ""
        assert len(report.findings) >= 1
        assert report.findings[0].title == "Fake Vendor — Ratio Consulting GmbH"
        assert report.findings[0].severity == "critical"
        assert report.findings[0].fraud_likelihood >= 0.9
        assert len(report.findings[0].evidence_references) >= 1
        assert len(report.timeline) >= 1
        assert len(report.entity_relationships) >= 1
        assert report.fraud_assessment.overall_likelihood >= 0.9
        assert "€248,000" in report.fraud_assessment.estimated_financial_impact
        assert len(report.fraud_assessment.schemes_identified) >= 1
        assert len(report.remaining_questions) >= 1


class TestTimelineReconstruction:
    def test_builds_timeline_from_buffer(self) -> None:
        state = _build_completed_state()
        timeline = reconstruct_timeline(state)
        assert len(timeline) == 3
        assert timeline[0].source == "Lieferantenbuchungen.txt"
        assert "Step 1" in timeline[0].date


class TestEntityRelationships:
    def test_extracts_relationships(self) -> None:
        store = _build_evidence_store()
        rels = extract_entity_relationships(store)
        # Should find vendor-amount and vendor-account relationships
        assert len(rels) >= 1


class TestFraudAssessment:
    def test_aggregates_likelihood(self) -> None:
        state = _build_completed_state()
        assessment = aggregate_fraud_assessment(state)
        assert assessment.overall_likelihood > 0.8
        # 0.7 * 0.92 + 0.3 * avg(0.85,0.92,0.90) = 0.644 + 0.267 = 0.911
        assert assessment.overall_likelihood <= 1.0

    def test_empty_buffer(self) -> None:
        state = InvestigationState()
        assessment = aggregate_fraud_assessment(state)
        assert assessment.overall_likelihood == 0.0
