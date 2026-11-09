from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from evidence_ledger_agent.corpus import (
    FICTIONAL_MARK,
    Corpus,
    CorpusIntegrityError,
    normalize_text,
    sha256_text,
)
from evidence_ledger_agent.retrieval import BM25Index, tokenize

from .conftest import FIXTURES


@pytest.mark.parametrize(
    "raw",
    [
        "  a\r\nb\t c  \n\n\n\nd  ",
        "Café at 25 °C\r\rline",
        "already normal\n\ntext",
        "",
    ],
)
def test_normalization_is_idempotent(raw: str) -> None:
    once = normalize_text(raw)
    assert normalize_text(once) == once


def test_normalization_composes_unicode_and_newlines() -> None:
    text = normalize_text("Café\r\nnext\t line   \n\n\n\nend")
    assert text == "Café\nnext  line\n\nend"


def test_unicode_offsets_are_code_points(dev_corpus: Corpus) -> None:
    doc = dev_corpus.get("dev-01")
    assert doc is not None
    pos = doc.text.index("25 °C")
    assert doc.text[pos : pos + 5] == "25 °C"
    assert len("°") == 1  # offsets index code points, not UTF-8 bytes


def test_every_document_is_marked_fictional(dev_corpus: Corpus, heldout_corpus: Corpus) -> None:
    for corpus in (dev_corpus, heldout_corpus):
        assert len(corpus) == 12
        for doc in corpus:
            assert doc.fictional and doc.text.startswith(FICTIONAL_MARK)


def test_documents_are_immutable_and_hashes_stable(dev_corpus: Corpus) -> None:
    doc = dev_corpus.get("dev-03")
    assert doc is not None
    with pytest.raises(ValidationError):
        doc.text = "tampered"  # type: ignore[misc]
    assert sha256_text(doc.text) == doc.sha256
    assert Corpus.load(FIXTURES / "corpus" / "dev").fingerprint() == dev_corpus.fingerprint()


def test_tampered_document_fails_hash_check(tmp_path: Path) -> None:
    folder = tmp_path / "dev"
    shutil.copytree(FIXTURES / "corpus" / "dev", folder)
    target = folder / "dev-06.txt"
    target.write_text(target.read_text(encoding="utf-8").replace("91%", "97%"), encoding="utf-8")
    with pytest.raises(CorpusIntegrityError):
        Corpus.load(folder)


def test_missing_fictional_mark_is_rejected(tmp_path: Path) -> None:
    folder = tmp_path / "c"
    folder.mkdir()
    (folder / "x.txt").write_text("A real-looking report.", encoding="utf-8")
    manifest = {
        "family": "c",
        "documents": [
            {"doc_id": "x", "file": "x.txt", "title": "t", "kind": "report", "date": "2024"}
        ],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusIntegrityError):
        Corpus.load(folder, verify=False)


def test_unknown_document_is_none(dev_corpus: Corpus) -> None:
    assert dev_corpus.get("dev-99") is None


def test_tokenizer_keeps_compounds_and_parts() -> None:
    toks = tokenize("The LX-4 nickel-iron film at 0.62 A cm-2")
    assert {"lx-4", "lx", "nickel-iron", "nickel", "iron", "0.62", "cm-2"} <= set(toks)
    assert "the" not in toks


def test_search_ranks_relevant_document_first(dev_index: BM25Index) -> None:
    hits = dev_index.search("LX-4 stable 100 hours pH 14", limit=3)
    assert hits[0]["doc_id"] == "dev-01"
    assert len(hits[0]["snippet"]) <= 200
    assert {"title", "conditions", "date", "supersedes", "length_chars"} <= set(hits[0])
    assert "verdict" not in hits[0] and "label" not in hits[0]


def test_search_is_deterministic_with_id_tiebreak(dev_index: BM25Index) -> None:
    a = dev_index.search("catalyst", limit=10)
    b = dev_index.search("catalyst", limit=10)
    assert a == b
    pairs = [(-h["score"], h["doc_id"]) for h in a]
    assert pairs == sorted(pairs)


def test_search_filters_on_metadata(dev_index: BM25Index) -> None:
    hits = dev_index.search("LX-4 stability", filters={"pH": "7"}, limit=10)
    assert [h["doc_id"] for h in hits] == ["dev-02"]


def test_empty_retrieval(dev_index: BM25Index) -> None:
    assert dev_index.search("zeolite desalination graphene") == []
    assert dev_index.search("the of and") == []
