"""Run one iterative agent episode and turn its state into a ledger entry."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .agentcore.adapters import ModelAdapter
from .agentcore.loop import AgentLoop, CheckpointStore
from .agentcore.policy import Budget, Policy, ToolRegistry
from .agentcore.trace import TraceWriter
from .corpus import Corpus
from .prompts import agent_system_prompt, render_observation
from .retrieval import BM25Index
from .schemas import LedgerEntry, LedgerState, Task, VerifiedCitation
from .tools import ALL_TOOLS, build_tools


class EpisodeConfig(BaseModel):
    """Per-episode settings shared by every task in an arm."""

    budget: Budget = Budget(max_steps=16, max_tool_calls=10)
    allowlist: tuple[str, ...] = ALL_TOOLS
    recent_k: int = 4
    record_timing: bool = True
    max_completion_tokens: int = 700


def make_registry(
    corpus: Corpus, cfg: EpisodeConfig, index: BM25Index | None = None
) -> ToolRegistry:
    """Registry over ``corpus`` restricted to the configured allowlist."""
    return ToolRegistry(build_tools(corpus, index), allowlist=cfg.allowlist)


def new_state(task: Task, arm: str, cfg: EpisodeConfig, run: int = 0) -> LedgerState:
    """Fresh state for one task. Gold information is never part of it."""
    return LedgerState(
        episode_id=f"{arm}:{task.task_id}:run{run}",
        task_id=task.task_id,
        question=task.question,
        conditions=task.conditions,
        remaining_tool_calls=cfg.budget.max_tool_calls,
    )


def run_episode(
    task: Task,
    corpus: Corpus,
    adapter: ModelAdapter,
    cfg: EpisodeConfig,
    arm: str = "agent",
    run: int = 0,
    trace_path: Path | None = None,
    checkpoint_path: Path | None = None,
    resume: bool = False,
    index: BM25Index | None = None,
) -> tuple[LedgerEntry, LedgerState]:
    """Run (or resume) one episode.

    Args:
        task: The question to audit.
        corpus: Document store the tools read from.
        adapter: Model adapter (fixture, replay or live).
        cfg: Budget, allowlist and prompt settings.
        arm: Arm name recorded in the ledger.
        run: Repeat index for multi-run evaluations.
        trace_path: JSONL trace output, if any.
        checkpoint_path: Checkpoint file, if any.
        resume: Load the checkpoint instead of starting fresh.
        index: Optional prebuilt BM25 index.

    Returns:
        The ledger entry and the final state.
    """
    registry = make_registry(corpus, cfg, index)
    store = CheckpointStore(checkpoint_path) if checkpoint_path else None
    state = store.load(LedgerState) if (resume and store) else None
    if state is None:
        state = new_state(task, arm, cfg, run)
    loop = AgentLoop(
        adapter,
        Policy(registry, cfg.budget),
        agent_system_prompt(registry),
        render_observation,
        checkpoint=store,
        trace=TraceWriter(trace_path, cfg.record_timing) if trace_path else None,
        recent_k=cfg.recent_k,
        max_completion_tokens=cfg.max_completion_tokens,
    )
    state = loop.run(state)
    return ledger_entry(task, arm, state), state


def ledger_entry(task: Task, arm: str, state: LedgerState) -> LedgerEntry:
    """Convert a finished state into an auditable ledger entry."""
    base = {
        "task_id": task.task_id,
        "question": task.question,
        "arm": arm,
        "stop_reason": state.stop_reason,
    }
    final = state.final or {}
    if state.status == "complete":
        return LedgerEntry(
            **base,
            outcome=final["verdict"],
            claim=final["claim"],
            conditions=final["conditions"],
            rationale=final["rationale"],
            citations=[VerifiedCitation(**c) for c in final["citations"]],
        )
    if state.status == "abstained":
        return LedgerEntry(**base, outcome="abstained", abstain_reason=final.get("reason"))
    return LedgerEntry(**base, outcome="failed")
