"""Domain records for the evidence ledger."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .agentcore.schemas import BaseAgentState

Verdict = Literal["supported", "conflicted", "insufficient"]
Outcome = Literal["supported", "conflicted", "insufficient", "abstained", "failed"]


class Document(BaseModel):
    """One normalized, immutable corpus document."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    title: str
    text: str
    sha256: str
    kind: str
    date: str
    conditions: dict[str, str] = Field(default_factory=dict)
    supersedes: str | None = None
    fictional: bool = True


class SpanRef(BaseModel):
    """A character range ``[start, end)`` of a document, bound to its hash."""

    model_config = ConfigDict(frozen=True)

    doc_id: str
    start: int
    end: int
    doc_hash: str

    @property
    def span_id(self) -> str:
        """Stable identifier ``doc_id:start:end``."""
        return f"{self.doc_id}:{self.start}:{self.end}"

    def contains(self, doc_id: str, start: int, end: int) -> bool:
        """True if ``[start, end)`` of ``doc_id`` lies inside this span."""
        return doc_id == self.doc_id and self.start <= start and end <= self.end


class VerifiedCitation(SpanRef):
    """A quote proven identical to the stored text at its offsets."""

    quote: str
    read_span_id: str


class Claim(BaseModel):
    """A claim recorded in the ledger with its verified citations."""

    verdict: Verdict
    text: str
    citations: list[VerifiedCitation]


class Task(BaseModel):
    """A question for the agent. Holds no gold information."""

    task_id: str
    family: str
    question: str
    conditions: dict[str, str] = Field(default_factory=dict)


class LedgerState(BaseAgentState):
    """Episode state for the evidence ledger agent."""

    task_id: str
    question: str
    conditions: dict[str, str] = Field(default_factory=dict)
    retrieved_ids: list[str] = Field(default_factory=list)
    inspected_spans: list[SpanRef] = Field(default_factory=list)
    provisional_claims: list[Claim] = Field(default_factory=list)
    finish_attempts: list[dict[str, Any]] = Field(default_factory=list)

    def observable(self) -> dict[str, Any]:
        """Compact summary shown to the model each step."""
        return {
            **super().observable(),
            "question": self.question,
            "stated_conditions": self.conditions,
            "documents_seen_in_search": self.retrieved_ids,
            "spans_read": [s.span_id for s in self.inspected_spans],
            "rejected_finish_attempts": sum(1 for a in self.finish_attempts if not a["accepted"]),
        }


class LedgerEntry(BaseModel):
    """Final, auditable record of one episode or baseline answer."""

    task_id: str
    question: str
    arm: str
    outcome: Outcome
    claim: str = ""
    conditions: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""
    citations: list[VerifiedCitation] = Field(default_factory=list)
    abstain_reason: str | None = None
    stop_reason: str | None = None
