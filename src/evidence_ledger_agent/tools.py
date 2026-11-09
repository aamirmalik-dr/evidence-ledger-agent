"""The five bounded tools the agent may call: search, read_span,
expand_context, finish and abstain.

All tools are finite, typed operations over an in-memory corpus. None writes
files, runs code or touches the network.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .agentcore import ToolFailure, ToolSpec
from .citation_checks import CitationArg, parse_span_id, resolve_citations
from .corpus import Corpus
from .retrieval import BM25Index
from .schemas import Claim, LedgerState, SpanRef, Verdict

MAX_READ_CHARS = 1500
MAX_RADIUS = 500
MAX_EXPANDED_CHARS = MAX_READ_CHARS + 2 * MAX_RADIUS
MAX_RATIONALE_WORDS = 80
ALL_TOOLS = ("search", "read_span", "expand_context", "finish", "abstain")


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=1, max_length=300)
    filters: dict[str, str] = Field(default_factory=dict, description="metadata, e.g. {'pH': '14'}")
    limit: int = Field(default=5, ge=1, le=10)


class ReadSpanArgs(_Args):
    doc_id: str
    start: int = Field(ge=0)
    end: int = Field(description=f"exclusive; end - start <= {MAX_READ_CHARS}")

    @model_validator(mode="after")
    def _range(self) -> ReadSpanArgs:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        if self.end - self.start > MAX_READ_CHARS:
            raise ValueError(f"a read is limited to {MAX_READ_CHARS} characters")
        return self


class ExpandContextArgs(_Args):
    span_id: str
    radius: int = Field(ge=1, le=MAX_RADIUS)


class FinishArgs(_Args):
    verdict: Verdict
    claim: str = Field(min_length=1, max_length=600, description="what the evidence establishes")
    citations: list[CitationArg] = Field(default_factory=list, max_length=8)
    conditions: dict[str, str] = Field(
        default_factory=dict, description="conditions under which the verdict holds"
    )
    rationale: str = Field(min_length=1, description=f"at most {MAX_RATIONALE_WORDS} words")

    @field_validator("rationale")
    @classmethod
    def _short(cls, v: str) -> str:
        if len(v.split()) > MAX_RATIONALE_WORDS:
            raise ValueError(f"rationale exceeds {MAX_RATIONALE_WORDS} words")
        return v


class AbstainArgs(_Args):
    reason: str = Field(min_length=1, max_length=400)


def _record_span(state: LedgerState, ref: SpanRef) -> None:
    if all(s.span_id != ref.span_id for s in state.inspected_spans):
        state.inspected_spans.append(ref)


def build_tools(corpus: Corpus, index: BM25Index | None = None) -> list[ToolSpec]:
    """Create the tool specs bound to one corpus.

    Args:
        corpus: The read-only document store.
        index: Optional prebuilt BM25 index over the same corpus.

    Returns:
        Specs for all five tools; the registry decides which are allowed.
    """
    index = index or BM25Index(corpus)

    def search(state: LedgerState, args: SearchArgs) -> dict[str, Any]:
        hits = index.search(args.query, args.filters, args.limit)
        for h in hits:
            if h["doc_id"] not in state.retrieved_ids:
                state.retrieved_ids.append(h["doc_id"])
        return {"query": args.query, "hits": hits}

    def _read(state: LedgerState, doc_id: str, start: int, end: int) -> dict[str, Any]:
        doc = corpus.get(doc_id)
        if doc is None:
            raise ToolFailure("not_found", f"unknown document {doc_id!r}")
        if start >= len(doc.text):
            raise ToolFailure("out_of_range", f"{doc_id} has {len(doc.text)} characters")
        end = min(end, len(doc.text))
        ref = SpanRef(doc_id=doc_id, start=start, end=end, doc_hash=doc.sha256)
        _record_span(state, ref)
        return {
            "span_id": ref.span_id,
            "doc_id": doc_id,
            "start": start,
            "end": end,
            "doc_length": len(doc.text),
            "doc_hash": doc.sha256,
            "text": doc.text[start:end],
        }

    def read_span(state: LedgerState, args: ReadSpanArgs) -> dict[str, Any]:
        return _read(state, args.doc_id, args.start, args.end)

    def expand_context(state: LedgerState, args: ExpandContextArgs) -> dict[str, Any]:
        parsed = parse_span_id(args.span_id)
        if parsed is None or all(s.span_id != args.span_id for s in state.inspected_spans):
            raise ToolFailure("precondition_failed", "expand only a span_id you have already read")
        doc_id, start, end = parsed
        new_start, new_end = max(0, start - args.radius), end + args.radius
        if new_end - new_start > MAX_EXPANDED_CHARS:
            raise ToolFailure("out_of_range", f"expanded span exceeds {MAX_EXPANDED_CHARS} chars")
        return _read(state, doc_id, new_start, new_end)

    def check_finish(state: LedgerState, args: FinishArgs) -> None:
        verified, problems = resolve_citations(corpus, state.inspected_spans, args.citations)
        reasons = [p.as_text() for p in problems]
        docs = {c.doc_id for c in verified}
        if args.verdict == "supported" and not args.citations:
            reasons.append("a supported verdict needs at least one citation")
        if args.verdict == "conflicted" and len(docs) < 2:
            reasons.append("a conflicted verdict needs citations from at least two documents")
        state.finish_attempts.append(
            {
                "step": state.steps,
                "verdict": args.verdict,
                "citations": len(args.citations),
                "valid_citations": len(verified),
                "accepted": not reasons,
                "problems": reasons,
            }
        )
        if reasons:
            raise ToolFailure("precondition_failed", "finish rejected: " + " | ".join(reasons))

    def finish(state: LedgerState, args: FinishArgs) -> dict[str, Any]:
        verified, _ = resolve_citations(corpus, state.inspected_spans, args.citations)
        state.provisional_claims.append(
            Claim(verdict=args.verdict, text=args.claim, citations=verified)
        )
        return {
            "verdict": args.verdict,
            "claim": args.claim,
            "conditions": args.conditions,
            "rationale": args.rationale,
            "citations": [c.model_dump() for c in verified],
        }

    def abstain(state: LedgerState, args: AbstainArgs) -> dict[str, Any]:
        return {"reason": args.reason}

    return [
        ToolSpec(
            "search",
            "Lexical search over the local corpus; returns ids, snippets and "
            "metadata, never labels.",
            SearchArgs,
            search,
        ),
        ToolSpec(
            "read_span",
            f"Read up to {MAX_READ_CHARS} characters of a document by "
            "offsets; returns text and a span_id.",
            ReadSpanArgs,
            read_span,
        ),
        ToolSpec(
            "expand_context",
            "Re-read a span you already read with extra characters on " "both sides.",
            ExpandContextArgs,
            expand_context,
        ),
        ToolSpec(
            "finish",
            "End with a verdict, a claim and verbatim quotes from spans you read.",
            FinishArgs,
            finish,
            precheck=check_finish,
            terminal="complete",
        ),
        ToolSpec(
            "abstain",
            "End without a verdict when the corpus cannot settle the question.",
            AbstainArgs,
            abstain,
            terminal="abstained",
        ),
    ]
