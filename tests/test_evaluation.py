from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence_ledger_agent.__main__ import main, run_demo, verify_ledger
from evidence_ledger_agent.agent import EpisodeConfig, make_registry
from evidence_ledger_agent.agentcore.adapters import FixtureAdapter
from evidence_ledger_agent.baselines import run_lexical, run_single_call, sentences
from evidence_ledger_agent.corpus import Corpus
from evidence_ledger_agent.evaluation import (
    aggregate,
    load_config,
    load_gold,
    load_tasks,
    run_evaluation,
    score_entry,
)
from evidence_ledger_agent.report import build_evidence
from evidence_ledger_agent.retrieval import BM25Index
from evidence_ledger_agent.schemas import LedgerEntry, LedgerState, VerifiedCitation
from evidence_ledger_agent.tools import ALL_TOOLS

from .conftest import FIXTURES, ROOT


@pytest.fixture(scope="module")
def dev_gold(dev_corpus: Corpus):
    return load_gold(ROOT / "evaluator" / "gold_dev.json", dev_corpus)


def test_every_gold_anchor_resolves_once_and_tasks_match(dev_corpus, heldout_corpus) -> None:
    for family, corpus in (("dev", dev_corpus), ("heldout", heldout_corpus)):
        gold = load_gold(ROOT / "evaluator" / f"gold_{family}.json", corpus)
        tasks = load_tasks(FIXTURES / f"questions_{family}.json")
        assert {t.task_id for t in tasks} == set(gold)
    assert len(load_tasks(FIXTURES / "questions_heldout.json")) == 10


def _cite(corpus: Corpus, doc_id: str, quote: str) -> VerifiedCitation:
    doc = corpus.get(doc_id)
    s = doc.text.index(quote)
    return VerifiedCitation(
        doc_id=doc_id,
        start=s,
        end=s + len(quote),
        doc_hash=doc.sha256,
        quote=quote,
        read_span_id=f"{doc_id}:0:{len(doc.text)}",
    )


def test_valid_quote_with_wrong_verdict_fails_support(dev_corpus, dev_gold) -> None:
    cit = _cite(
        dev_corpus, "dev-01", "All three LX-4 electrodes remained stable for the full 100 hours"
    )
    wrong = LedgerEntry(
        task_id="dev-q1", question="q", arm="x", outcome="supported", citations=[cit]
    )
    s = score_entry(wrong, dev_gold["dev-q1"])
    assert s["verdict_correct"] == 0 and s["supporting_citations"] == 0
    assert s["unsupported_claim"] == 1 and s["covered_groups"] == 0


def test_conflict_with_both_sides_and_condition(dev_corpus, dev_gold) -> None:
    entry = LedgerEntry(
        task_id="dev-q1",
        question="q",
        arm="x",
        outcome="conflicted",
        conditions={"pH": "14 vs 7"},
        citations=[
            _cite(dev_corpus, "dev-01", "remained stable for the full 100 hours at pH 14"),
            _cite(dev_corpus, "dev-02", "At pH 7 the LX-4 electrodes were not stable"),
        ],
    )
    s = score_entry(entry, dev_gold["dev-q1"])
    assert s["contradiction_hit"] == 1 and s["covered_groups"] == 2
    assert s["condition_terms_found"] == 1 and s["unsupported_claim"] == 0


def test_abstention_scoring(dev_gold) -> None:
    abst = LedgerEntry(task_id="t", question="q", arm="x", outcome="abstained")
    assert score_entry(abst, dev_gold["dev-q5"])["verdict_correct"] == 1
    assert score_entry(abst, dev_gold["dev-q3"])["verdict_correct"] == 0  # corpus settles q3
    failed = LedgerEntry(task_id="t", question="q", arm="x", outcome="failed")
    s = score_entry(failed, dev_gold["dev-q6"])
    assert s["verdict_correct"] == 0 and s["failed"] == 1


def test_sentence_splitter_keeps_decimals() -> None:
    text = "Value was 0.62 A cm-2 at 1.8 V. Next sentence here.\nNew line."
    parts = [text[s:e] for s, e in sentences(text)]
    assert parts == ["Value was 0.62 A cm-2 at 1.8 V.", "Next sentence here.", "New line."]


def test_lexical_baseline_is_deterministic(dev_corpus) -> None:
    index = BM25Index(dev_corpus)
    task = load_tasks(FIXTURES / "questions_dev.json")[5]
    a, _ = run_lexical(task, dev_corpus, index, 0.5)
    b, _ = run_lexical(task, dev_corpus, index, 0.5)
    assert a == b and a.outcome == "supported" and a.citations[0].doc_id == "dev-09"


def test_single_call_counts_invalid_citation_and_reprompts(dev_corpus) -> None:
    index = BM25Index(dev_corpus)
    task = load_tasks(FIXTURES / "questions_dev.json")[5]
    reply = {
        "verdict": "supported",
        "claim": "c",
        "rationale": "r",
        "conditions": {},
        "citations": [
            {"span_id": "dev-09:0:957", "quote": "calcined in air at 450 °C"},
            {"span_id": "dev-09:0:957", "quote": "calcined at 450 C in air"},
            {"span_id": "dev-09:0:957", "quote": "short"},
        ],
    }
    entry, info = run_single_call(
        task, dev_corpus, index, FixtureAdapter(["not json", reply]), top_k=4
    )
    assert entry.outcome == "supported" and len(entry.citations) == 1
    assert (info["citations_emitted"], info["citations_valid"]) == (3, 1)
    assert info["quote_mismatches"] == 1 and info["reprompts"] == 1 and info["model_calls"] == 2
    entry, info = run_single_call(task, dev_corpus, index, FixtureAdapter(["x", "y"]), top_k=4)
    assert entry.outcome == "failed" and info["malformed_actions"] == 1


def test_gold_is_unreachable_from_tools_and_state(dev_corpus) -> None:
    registry = make_registry(dev_corpus, EpisodeConfig())
    described = json.dumps(registry.describe())
    assert {t["name"] for t in registry.describe()} == set(ALL_TOOLS)
    for word in ("gold", "evaluator", "path", "file"):
        assert word not in described.lower()
    assert not any(k in LedgerState.model_fields for k in ("gold", "verdict", "answer"))


def test_fixture_evaluation_end_to_end(tmp_path: Path) -> None:
    cfg, sha = load_config(ROOT / "configs" / "fixture.yaml")
    cfg = cfg.model_copy(
        update={"output_dir": str(tmp_path / "out"), "checkpoint_dir": str(tmp_path / "ck")}
    )
    out = run_evaluation(cfg, sha, ROOT)
    rows = [json.loads(x) for x in (out / "task_results.jsonl").read_text().splitlines()]
    assert len(rows) == (6 + 10) * 4
    comp = {(r["family"], r["arm"]): r for r in aggregate(rows)}
    assert comp[("heldout", "agent")]["failures"] == 1  # planted tool-call budget stop
    assert comp[("dev", "agent")]["rejected_finishes"] == 1  # planted fabricated quote
    assert comp[("dev", "agent")]["reprompts"] == 1  # planted malformed reply
    assert comp[("dev", "single_call")]["citation_validity_k"] == 5
    assert verify_ledger(out / "ledger.json", ROOT) == []
    traces = list((out / "traces").rglob("*.jsonl"))
    assert len(traces) == 2 * 16 + 0  # agent and agent_no_expand, one per task
    text = "".join(t.read_text(encoding="utf-8") for t in traces)
    assert "Users" not in text and ":\\\\" not in text
    # a second run reproduces the same ledger and results byte for byte
    first = (out / "ledger.json").read_text(), (out / "task_results.jsonl").read_text()
    run_evaluation(cfg, sha, ROOT)
    assert ((out / "ledger.json").read_text(), (out / "task_results.jsonl").read_text()) == first


def test_evidence_lists_every_failure_and_marks_live_pending(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "reports").mkdir(parents=True)
    cfg, sha = load_config(ROOT / "configs" / "fixture.yaml")
    rows_dir = run_evaluation(
        cfg.model_copy(
            update={
                "output_dir": str(root / "reports" / "fixture"),
                "checkpoint_dir": str(tmp_path / "ck"),
            }
        ),
        sha,
        ROOT,
    )
    evidence = build_evidence(root)
    assert evidence["modes"]["live"] == "pending"
    fixture = evidence["modes"]["fixture"]
    rows = [json.loads(x) for x in (rows_dir / "task_results.jsonl").read_text().splitlines()]
    wrong = {(r["arm"], r["task_id"]) for r in rows if not r["verdict_correct"]}
    listed = {(f["arm"], f["task_id"]) for f in fixture["failures"]}
    assert wrong <= listed and ("agent", "ho-q05") in listed


def test_require_live_fails_clearly(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    for var in ("AGENT_MODEL_BASE_URL", "AGENT_MODEL_NAME", "AGENT_MODEL_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(ROOT)
    assert main(["evaluate", "--config", "configs/fixture.yaml", "--require-live"]) == 2
    assert main(["evaluate", "--config", "configs/live.yaml", "--require-live"]) == 2
    assert "fixture fallback is disabled" in " ".join(capsys.readouterr().out.split())
    assert not (ROOT / "reports" / "live" / "run_meta.json").exists()


def test_demo_reproduces_committed_ledger() -> None:
    entries = run_demo("fixture", ROOT)
    committed = json.loads((ROOT / "reports" / "demo_ledger.json").read_text(encoding="utf-8"))
    assert [e.model_dump() for e in entries] == committed
    assert [e.outcome for e in entries] == ["conflicted", "abstained"]


def test_headline_table_holds_only_real_measurements(tmp_path: Path) -> None:
    from evidence_ledger_agent.report import build_evidence, metrics_table, scorer_table

    root = Path(__file__).resolve().parents[1]
    evidence = build_evidence(root)
    headline, scorer = metrics_table(evidence), scorer_table(evidence)
    assert "fixture, scripted" not in headline and "no model, deterministic" in headline
    assert "fixture, scripted" in scorer and "| lexical |" not in scorer
