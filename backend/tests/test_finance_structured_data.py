from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.agents.finance import run_finance_agent
from app.investigation.structured import (
    KeyValueEntry,
    StructuredFile,
    format_financial_key_figures,
    normalize_financial_metrics,
)
from app.schemas import PipelineContext, SourceKind


class CapturingGeminiClient:
    def __init__(self) -> None:
        self.user = ""

    async def generate(self, **kwargs: object) -> str:
        self.user = str(kwargs["user"])
        return "- Q: Revenue?\n  A: €10 million"


@pytest.mark.asyncio
async def test_finance_prompt_includes_pre_extracted_figures() -> None:
    client = CapturingGeminiClient()

    await run_finance_agent(
        source_text="Raw quarterly report text.",
        pipeline_context=PipelineContext(source_kind=SourceKind.PDF),
        gemini_client=client,  # type: ignore[arg-type]
        key_figures="report.pdf:\n- revenue: €10 million (Q1 2025)",
    )

    assert "Key Figures" in client.user
    assert "revenue: €10 million" in client.user
    assert "Raw quarterly report text." in client.user


def test_multi_pdf_figures_normalize_to_shared_metric_names() -> None:
    files = [
        StructuredFile(
            file_id="q1",
            filename="q1.pdf",
            extraction_method="llm_assisted",
            key_values=[
                KeyValueEntry(field="Revenue", value="€10 million", context="Q1 2025"),
                KeyValueEntry(field="Earnings per share", value="€1.20", context="Q1 2025"),
            ],
        ),
        StructuredFile(
            file_id="q2",
            filename="q2.pdf",
            extraction_method="llm_assisted",
            key_values=[
                KeyValueEntry(field="Net Sales", value="€12 million", context="Q2 2025"),
                KeyValueEntry(field="Operating Margin", value="18%", context="Q2 2025"),
            ],
        ),
    ]

    normalized = normalize_financial_metrics(files)
    summary = format_financial_key_figures(normalized)

    assert [entry.field for entry in normalized[0].key_values or []] == ["revenue", "eps"]
    assert [entry.field for entry in normalized[1].key_values or []] == ["revenue", "operating_margin"]
    assert summary.count("revenue:") == 2
