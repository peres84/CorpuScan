from __future__ import annotations

from pydantic import BaseModel, Field


class InvestigationBufferRow(BaseModel):
    doc_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    notes_summary: str = Field(default="")
    fraud_likelihood: float = Field(ge=0.0, le=1.0, default=0.0)
    primary_next_doc: str | None = None
    alt_doc_leads: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class InvestigationState(BaseModel):
    buffer: list[InvestigationBufferRow] = Field(default_factory=list)
    visited: set[str] = Field(default_factory=set)
    stack: list[str] = Field(default_factory=list)  # DFS backtracking stack
    overall_fraud_likelihood: float = Field(ge=0.0, le=1.0, default=0.0)
    iteration_count: int = Field(ge=0, default=0)
    max_iterations: int = Field(ge=1, default=50)

    def is_terminated(self) -> bool:
        """Check if the investigation should stop."""
        if self.iteration_count >= self.max_iterations:
            return True
        if not self.stack and self.iteration_count > 0:
            return True
        return False

    def add_visited(self, doc_id: str) -> None:
        self.visited.add(doc_id)
        self.iteration_count += 1

    def update_overall_likelihood(self) -> None:
        """Compute overall fraud likelihood as max of individual document likelihoods."""
        if self.buffer:
            self.overall_fraud_likelihood = max(row.fraud_likelihood for row in self.buffer)

    def format_buffer_for_llm(self) -> str:
        """Format the investigation buffer as a readable string for the LLM context."""
        if not self.buffer:
            return "No previous investigation steps."

        lines: list[str] = []
        for idx, row in enumerate(self.buffer, start=1):
            lines.append(
                f"Step {idx}: {row.filename}\n"
                f"  Notes: {row.notes_summary}\n"
                f"  Fraud likelihood: {row.fraud_likelihood:.2f}\n"
                f"  Next lead: {row.primary_next_doc or 'none'}\n"
                f"  Open questions: {'; '.join(row.open_questions) if row.open_questions else 'none'}"
            )
        return "\n\n".join(lines)
