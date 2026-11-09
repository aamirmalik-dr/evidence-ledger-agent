"""Two baselines that see the same corpus as the agent.

- ``lexical``: no model. BM25 top document, best-covering sentence, and a
  fixed coverage threshold decide between "supported" and "insufficient".
- ``single_call``: the same model as the agent, one call, over the same BM25
  top-k passages, with no ability to search or read further.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from pydantic import ValidationError

from .agentcore.adapters import AdapterError, ModelAdapter
from .citation_checks import CitationArg, resolve_citations
from .corpus import Corpus
from .prompts import SINGLE_CALL_SYSTEM, single_call_user
from .retrieval import BM25Index, tokenize
from .schemas import LedgerEntry, SpanRef, Task
from .tools import MAX_RATIONALE_WORDS, MAX_READ_CHARS

QUESTION_FILLER = frozenset({"claim", "check"})
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n+")


def sentences(text: str) -> list[tuple[int, int]]:
    """Character ranges of sentences; decimal points never split a sentence."""
    spans, start = [], 0
    for m in _BOUNDARY.finditer(text):
        if text[start : m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _empty_info() -> dict[str, Any]:
    return {
        "model_calls": 0,
        "tool_calls": 0,
        "steps": 0,
        "prompt_chars": 0,
        "prompt_tokens": None,
        "completion_tokens": None,
        "latency_s": 0.0,
        "malformed_actions": 0,
        "reprompts": 0,
        "citations_emitted": 0,
        "citations_valid": 0,
        "quote_mismatches": 0,
        "rejected_finishes": 0,
    }


def run_lexical(
    task: Task, corpus: Corpus, index: BM25Index, threshold: float
) -> tuple[LedgerEntry, dict[str, Any]]:
    """Non-LLM baseline.

    Args:
        task: Question to answer.
        corpus: Document store.
        index: BM25 index over ``corpus``.
        threshold: Minimum fraction of query terms the best sentence must
            contain for a "supported" verdict. Fixed in the config before any
            evaluation run.

    Returns:
        Ledger entry and accounting info.
    """
    info = _empty_info()
    start_t = time.perf_counter()
    terms = set(tokenize(task.question)) - QUESTION_FILLER
    hits = index.search(task.question, limit=1)
    base = {"task_id": task.task_id, "question": task.question, "arm": "lexical"}
    if not hits or not terms:
        info["latency_s"] = time.perf_counter() - start_t
        return LedgerEntry(**base, outcome="insufficient", rationale="no lexical match"), info
    doc = corpus.get(hits[0]["doc_id"])
    assert doc is not None
    best, best_cov = None, -1.0
    for s, e in sentences(doc.text):
        cov = len(terms & set(tokenize(doc.text[s:e]))) / len(terms)
        if cov > best_cov:
            best, best_cov = (s, e), cov
    assert best is not None
    info["latency_s"] = time.perf_counter() - start_t
    rationale = f"best sentence covers {best_cov:.2f} of query terms (threshold {threshold})"
    if best_cov < threshold:
        return LedgerEntry(**base, outcome="insufficient", rationale=rationale), info
    s, e = best
    ref = SpanRef(doc_id=doc.doc_id, start=0, end=len(doc.text), doc_hash=doc.sha256)
    verified, _ = resolve_citations(
        corpus, [ref], [CitationArg(span_id=ref.span_id, quote=doc.text[s:e])]
    )
    info["citations_emitted"] = info["citations_valid"] = len(verified)
    return (
        LedgerEntry(
            **base,
            outcome="supported",
            claim=doc.text[s:e],
            rationale=rationale,
            citations=verified,
        ),
        info,
    )


def passages_for(task: Task, corpus: Corpus, index: BM25Index, top_k: int) -> list[dict]:
    """The top-k BM25 documents, each truncated to one read window."""
    out = []
    for hit in index.search(task.question, limit=top_k):
        doc = corpus.get(hit["doc_id"])
        assert doc is not None
        end = min(len(doc.text), MAX_READ_CHARS)
        out.append(
            {
                "span_id": f"{doc.doc_id}:0:{end}",
                "doc_id": doc.doc_id,
                "end": end,
                "doc_hash": doc.sha256,
                "title": doc.title,
                "kind": doc.kind,
                "conditions": doc.conditions,
                "supersedes": doc.supersedes,
                "text": doc.text[:end],
            }
        )
    return out


def _parse_answer(text: str) -> tuple[dict | None, str | None]:
    body = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    a, b = body.find("{"), body.rfind("}")
    if a < 0 or b <= a:
        return None, "no JSON object found"
    try:
        obj = json.loads(body[a : b + 1])
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc.msg}"
    if not isinstance(obj, dict):
        return None, "expected a JSON object"
    if "abstain" in obj:
        return obj, None
    if obj.get("verdict") not in ("supported", "conflicted", "insufficient"):
        return None, "verdict must be supported, conflicted or insufficient"
    if not isinstance(obj.get("citations", []), list):
        return None, "citations must be a list"
    return obj, None


def run_single_call(
    task: Task,
    corpus: Corpus,
    index: BM25Index,
    adapter: ModelAdapter,
    top_k: int,
    max_completion_tokens: int = 900,
    max_output_chars: int = 6000,
) -> tuple[LedgerEntry, dict[str, Any]]:
    """Single-call LLM baseline with one corrective re-prompt on malformed output.

    Citations are checked against the passages the model was shown. Invalid
    citations are dropped from the ledger and counted.
    """
    info = _empty_info()
    base = {"task_id": task.task_id, "question": task.question, "arm": "single_call"}
    passages = passages_for(task, corpus, index, top_k)
    shown = [
        SpanRef(doc_id=p["doc_id"], start=0, end=p["end"], doc_hash=p["doc_hash"]) for p in passages
    ]
    messages = [
        {"role": "system", "content": SINGLE_CALL_SYSTEM},
        {"role": "user", "content": single_call_user(task.question, passages)},
    ]
    obj, error = None, None
    for attempt in range(2):
        info["prompt_chars"] += sum(len(m["content"]) for m in messages)
        try:
            resp = adapter.complete(messages, max_completion_tokens)
        except AdapterError:
            return LedgerEntry(**base, outcome="failed", stop_reason="adapter_error"), info
        info["model_calls"] += 1
        info["latency_s"] += resp.latency_s
        for key, val in (
            ("prompt_tokens", resp.prompt_tokens),
            ("completion_tokens", resp.completion_tokens),
        ):
            if val is not None:
                info[key] = (info[key] or 0) + val
        if len(resp.text) > max_output_chars:
            obj, error = None, f"reply exceeded {max_output_chars} characters"
        else:
            obj, error = _parse_answer(resp.text)
        if obj is not None:
            break
        if attempt == 0:
            info["reprompts"] += 1
            messages += [
                {"role": "assistant", "content": resp.text[:max_output_chars]},
                {
                    "role": "user",
                    "content": f"Your reply could not be used: {error}. "
                    "Reply with exactly one JSON object as specified.",
                },
            ]
    if obj is None:
        info["malformed_actions"] += 1
        return LedgerEntry(**base, outcome="failed", stop_reason="malformed_output"), info
    if "abstain" in obj:
        reason = str(obj["abstain"])[:400]
        return (
            LedgerEntry(
                **base, outcome="abstained", abstain_reason=reason, stop_reason="abstained"
            ),
            info,
        )
    cits, malformed = [], 0
    for raw in obj.get("citations", []):
        try:
            cits.append(CitationArg.model_validate(raw))
        except ValidationError:
            malformed += 1
    verified, problems = resolve_citations(corpus, shown, cits)
    info["citations_emitted"] = len(cits) + malformed
    info["citations_valid"] = len(verified)
    info["quote_mismatches"] = sum(p.code == "quote_mismatch" for p in problems)
    rationale = " ".join(str(obj.get("rationale", "")).split()[:MAX_RATIONALE_WORDS])
    conditions = obj.get("conditions") if isinstance(obj.get("conditions"), dict) else {}
    return (
        LedgerEntry(
            **base,
            outcome=obj["verdict"],
            claim=str(obj.get("claim", ""))[:600],
            conditions={str(k): str(v) for k, v in conditions.items()},
            rationale=rationale,
            citations=verified,
            stop_reason="finished",
        ),
        info,
    )
