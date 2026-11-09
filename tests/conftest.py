from __future__ import annotations

from pathlib import Path

import pytest

from evidence_ledger_agent.corpus import Corpus
from evidence_ledger_agent.retrieval import BM25Index
from evidence_ledger_agent.schemas import LedgerState

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def dev_corpus() -> Corpus:
    return Corpus.load(FIXTURES / "corpus" / "dev")


@pytest.fixture(scope="session")
def heldout_corpus() -> Corpus:
    return Corpus.load(FIXTURES / "corpus" / "heldout")


@pytest.fixture(scope="session")
def dev_index(dev_corpus: Corpus) -> BM25Index:
    return BM25Index(dev_corpus)


def make_state(task_id: str = "t1", question: str = "q", calls: int = 10) -> LedgerState:
    return LedgerState(
        episode_id=f"test:{task_id}", task_id=task_id, question=question, remaining_tool_calls=calls
    )
