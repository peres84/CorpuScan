from __future__ import annotations

from app.agents._prompts import load_prompt
from app.integrations.gemini import GeminiClient
from app.schemas import PdfTemplateId, PipelineContext, SourceKind

PDF_TEMPLATE_INSTRUCTIONS: dict[PdfTemplateId, str] = {
    PdfTemplateId.GROWTH_COMPARISON: (
        "Template focus: Growth Comparison.\n"
        "- Prioritize revenue growth, segment drivers, acceleration or deceleration, "
        "constant-currency deltas, and relative momentum across the uploaded periods.\n"
        "- Surface who improved, who slowed, and what operational line items explain the change."
    ),
    PdfTemplateId.EARNINGS_COMPARISON: (
        "Template focus: Earnings Comparison.\n"
        "- Prioritize gross margin, operating margin, EPS, operating leverage, "
        "earnings quality, and material one-offs affecting profitability.\n"
        "- Surface whether earnings improved through mix, efficiency, pricing, or non-recurring items."
    ),
}


async def run_finance_agent(
    *,
    source_text: str,
    pipeline_context: PipelineContext,
    gemini_client: GeminiClient,
) -> str:
    prompt = load_prompt("finance")
    user = prompt.user_template.format(
        source_text=source_text,
        comparison_instructions=build_finance_context_block(pipeline_context),
    )
    return await gemini_client.generate(
        system=prompt.system,
        user=user,
        model=prompt.model,
        temperature=prompt.temperature,
        response_mime_type=prompt.response_mime_type,
    )


def build_finance_context_block(pipeline_context: PipelineContext) -> str:
    if pipeline_context.source_kind is not SourceKind.PDF:
        return "Source mode: single non-PDF source. Use the default analysis behavior."

    lines = [
        "Source mode: PDF comparison mode.",
        f"Uploaded PDF count: {len(pipeline_context.pdf_documents)}.",
        "Comparison requirements:",
        "- Treat each labeled document as a distinct source period.",
        "- Compare only within the provided company and provided periods.",
        "- Call out changes between the uploaded periods explicitly by period label.",
    ]
    if pipeline_context.template_id is not None:
        lines.append(PDF_TEMPLATE_INSTRUCTIONS[pipeline_context.template_id])
    return "\n".join(lines)
