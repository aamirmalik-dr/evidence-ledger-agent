"""Citation validation: quote identity and provenance, not scientific support.

These checks prove that a quoted string exists verbatim at stated offsets of
a known, unmodified document, and that the agent actually read that span.
Whether the quote supports the claim is judged separately by the evaluator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .corpus import Corpus
from .schemas import LedgerEntry, SpanRef, VerifiedCitation

MIN_QUOTE_CHARS = 8
MAX_QUOTE_CHARS = 600


class CitationArg(BaseModel):
    """A citation as proposed by a model: a read span and a verbatim quote."""

    span_id: str = Field(description="span_id returned by read_span or expand_context")
    quote: str = Field(
        min_length=MIN_QUOTE_CHARS,
        max_length=MAX_QUOTE_CHARS,
        description="exact text copied from inside that span (line breaks may be spaces)",
    )


@dataclass(frozen=True)
class CitationProblem:
    """Why a proposed citation was rejected."""

    index: int
    span_id: str
    code: str
    message: str

    def as_text(self) -> str:
        """Human-readable one-liner."""
        return f"citation {self.index} ({self.span_id}): {self.code}, {self.message}"


def parse_span_id(span_id: str) -> tuple[str, int, int] | None:
    """Split ``doc_id:start:end``; None if malformed."""
    parts = span_id.rsplit(":", 2)
    if len(parts) != 3:
        return None
    doc_id, start, end = parts
    if not (start.isdigit() and end.isdigit()) or int(end) <= int(start):
        return None
    return doc_id, int(start), int(end)


def check_span(corpus: Corpus, doc_id: str, start: int, end: int) -> str | None:
    """Return an error code if the range is not a valid span of a known document."""
    doc = corpus.get(doc_id)
    if doc is None:
        return "unknown_document"
    if not 0 <= start < end <= len(doc.text):
        return "offsets_out_of_range"
    return None


def find_quote(text: str, quote: str, start: int, end: int) -> tuple[int, int, bool] | None:
    """Locate ``quote`` inside ``text[start:end]``.

    An exact match is tried first. Failing that, runs of whitespace in the
    quote match any run of whitespace in the text, so a quote that turns a
    paragraph break into a space is still found. Nothing else is tolerated:
    every non-space character must match exactly.

    Returns:
        ``(match_start, match_end, whitespace_normalized)`` or None.
    """
    pos = text.find(quote, start, end)
    if pos >= 0:
        return pos, pos + len(quote), False
    words = quote.split()
    if not words:
        return None
    match = re.compile(r"\s+".join(re.escape(w) for w in words)).search(text, start, end)
    if match is None:
        return None
    return match.start(), match.end(), True


def resolve_citation(
    corpus: Corpus, read_spans: list[SpanRef], index: int, cit: CitationArg
) -> VerifiedCitation | CitationProblem:
    """Turn a proposed citation into a verified one, or explain the rejection.

    The quote must occur verbatim inside a span the agent read in this
    episode, up to whitespace (see ``find_quote``). The returned citation
    carries the exact stored text, its offsets and the document hash, so a
    later audit is byte-exact.
    """
    parsed = parse_span_id(cit.span_id)
    if parsed is None:
        return CitationProblem(index, cit.span_id, "malformed_span_id", "expected doc_id:start:end")
    doc_id, start, end = parsed
    code = check_span(corpus, doc_id, start, end)
    if code is not None:
        return CitationProblem(index, cit.span_id, code, "span does not exist in the corpus")
    if not any(s.contains(doc_id, start, end) for s in read_spans):
        return CitationProblem(index, cit.span_id, "span_not_read", "cite only spans you have read")
    doc = corpus.get(doc_id)
    assert doc is not None
    found = find_quote(doc.text, cit.quote, start, end)
    if found is None:
        return CitationProblem(
            index, cit.span_id, "quote_mismatch", "quote is not verbatim text of that span"
        )
    q_start, q_end, normalized = found
    return VerifiedCitation(
        doc_id=doc_id,
        start=q_start,
        end=q_end,
        doc_hash=doc.sha256,
        quote=doc.text[q_start:q_end],
        read_span_id=cit.span_id,
        whitespace_normalized=normalized,
    )


def resolve_citations(
    corpus: Corpus, read_spans: list[SpanRef], citations: list[CitationArg]
) -> tuple[list[VerifiedCitation], list[CitationProblem]]:
    """Resolve every citation; return the verified ones and the problems."""
    ok: list[VerifiedCitation] = []
    bad: list[CitationProblem] = []
    for i, cit in enumerate(citations):
        res = resolve_citation(corpus, read_spans, i, cit)
        (ok if isinstance(res, VerifiedCitation) else bad).append(res)  # type: ignore[arg-type]
    return ok, bad


def audit_citation(corpus: Corpus, cit: VerifiedCitation) -> str | None:
    """Re-check a stored citation against the corpus. None means it holds."""
    code = check_span(corpus, cit.doc_id, cit.start, cit.end)
    if code is not None:
        return code
    doc = corpus.get(cit.doc_id)
    assert doc is not None
    if doc.sha256 != cit.doc_hash:
        return "document_hash_changed"
    if doc.text[cit.start : cit.end] != cit.quote:
        return "quote_mismatch"
    return None


def audit_entry(corpus: Corpus, entry: LedgerEntry) -> list[str]:
    """Problems found in every citation of a ledger entry."""
    problems = []
    for i, cit in enumerate(entry.citations):
        code = audit_citation(corpus, cit)
        if code is not None:
            problems.append(f"{entry.task_id} citation {i} ({cit.span_id}): {code}")
    return problems
