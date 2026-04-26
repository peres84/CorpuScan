from __future__ import annotations

from app.agents._prompts import load_prompt
from app.integrations.gemini import GeminiClient
from app.schemas import PipelineContext, Script, SourceKind


async def run_scripter_agent(
    *,
    qa_markdown: str,
    pipeline_context: PipelineContext,
    gemini_client: GeminiClient,
) -> Script:
    prompt = load_prompt("scripter")
    user = prompt.user_template.format(
        qa_markdown=qa_markdown,
        storytelling_instructions=build_scripter_context_block(pipeline_context),
    )
    response_text = await gemini_client.generate(
        system=prompt.system,
        user=user,
        model=prompt.model,
        temperature=prompt.temperature,
        response_mime_type=prompt.response_mime_type,
    )
    return Script.model_validate_json(response_text)


def build_scripter_context_block(pipeline_context: PipelineContext) -> str:
    if pipeline_context.source_kind is not SourceKind.PDF:
        return "Story mode: standard single-source briefing."

    return "\n".join(
        [
            "Story mode: PDF comparison briefing.",
            "Use the four scenes as:",
            "- Scene 1: headline winner or key change across the uploaded periods.",
            "- Scene 2: the main driver behind that change.",
            "- Scene 3: a divergence, risk, or counter-signal that complicates the story.",
            "- Scene 4: the takeaway and what it implies for the next period or outlook.",
            "Name periods explicitly when comparing figures.",
        ]
    )
