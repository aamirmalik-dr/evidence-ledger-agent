"""Local lexical search (Okapi BM25) with deterministic tie-breaking.

Retrieval returns text and manifest metadata only, never evidence labels.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from .corpus import Corpus

_TOKEN = re.compile(r"[^\W_]+(?:[-.][^\W_]+)*")
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
        "which",
        "than",
        "then",
        "into",
        "over",
        "under",
        "after",
        "before",
        "not",
        "no",
    ]
)
SNIPPET_CHARS = 200


def tokenize_with_offsets(text: str) -> list[tuple[str, int]]:
    """Lower-case content tokens with their character offsets.

    Hyphenated tokens such as ``LX-4`` or ``nickel-iron`` are kept whole and
    also emitted as their parts, so both forms match.
    """
    out: list[tuple[str, int]] = []
    for m in _TOKEN.finditer(text):
        tok = m.group().lower()
        if tok in STOPWORDS:
            continue
        out.append((tok, m.start()))
        if "-" in tok:
            out.extend((p, m.start()) for p in tok.split("-") if p and p not in STOPWORDS)
    return out


def tokenize(text: str) -> list[str]:
    """Content tokens of ``text`` without offsets."""
    return [t for t, _ in tokenize_with_offsets(text)]


class BM25Index:
    """BM25 index over a corpus.

    Args:
        corpus: Documents to index.
        k1: Term-frequency saturation.
        b: Length normalization.
    """

    def __init__(self, corpus: Corpus, k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus, self.k1, self.b = corpus, k1, b
        self._tf = {d.doc_id: Counter(tokenize(d.text)) for d in corpus}
        self._len = {k: sum(v.values()) for k, v in self._tf.items()}
        self._avg = sum(self._len.values()) / max(len(self._len), 1)
        df: Counter[str] = Counter()
        for tf in self._tf.values():
            df.update(tf.keys())
        n = len(self._tf)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query: str) -> dict[str, float]:
        """BM25 score of every document for ``query``."""
        terms = set(tokenize(query))
        scores = {}
        for doc_id, tf in self._tf.items():
            norm = self.k1 * (1 - self.b + self.b * self._len[doc_id] / self._avg)
            s = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            scores[doc_id] = s
        return scores

    def search(
        self, query: str, filters: dict[str, str] | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Ranked hits with snippets and manifest metadata.

        Args:
            query: Free-text query.
            filters: Metadata constraints matched case-insensitively against
                a document's conditions and its ``kind``.
            limit: Maximum hits returned.

        Returns:
            Hits sorted by score, ties broken by document id.
        """
        filters = {k.lower(): v.lower() for k, v in (filters or {}).items()}
        ranked = []
        for doc_id, s in self.score(query).items():
            if s <= 0:
                continue
            doc = self.corpus.get(doc_id)
            assert doc is not None
            meta = {k.lower(): v.lower() for k, v in doc.conditions.items()} | {"kind": doc.kind}
            if any(meta.get(k) != v for k, v in filters.items()):
                continue
            ranked.append((-round(s, 9), doc_id))
        hits = []
        for neg, doc_id in sorted(ranked)[:limit]:
            doc = self.corpus.get(doc_id)
            assert doc is not None
            start = self._snippet_start(doc.text, query)
            end = min(len(doc.text), start + SNIPPET_CHARS)
            hits.append(
                {
                    "doc_id": doc_id,
                    "score": round(-neg, 4),
                    "title": doc.title,
                    "kind": doc.kind,
                    "date": doc.date,
                    "conditions": doc.conditions,
                    "supersedes": doc.supersedes,
                    "length_chars": len(doc.text),
                    "snippet_start": start,
                    "snippet_end": end,
                    "snippet": doc.text[start:end],
                }
            )
        return hits

    def _snippet_start(self, text: str, query: str) -> int:
        terms = set(tokenize(query))
        positions = [pos for tok, pos in tokenize_with_offsets(text) if tok in terms]
        if not positions:
            return 0
        best = max(
            positions, key=lambda p: (sum(p <= q < p + SNIPPET_CHARS for q in positions), -p)
        )
        start = max(0, best - 20)
        while start > 0 and not text[start - 1].isspace() and best - start < 40:
            start -= 1
        return start
