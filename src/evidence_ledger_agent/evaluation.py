"""Rubric scoring, the evaluation runner and per-arm comparison.

Gold labels are read from the evaluator/ folder by this module only. They are
never placed in agent state, never passed to a tool, and never shown to a model.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from . import __version__
from .agent import EpisodeConfig, make_registry, run_episode
from .agentcore import AGENTCORE_VERSION
from .agentcore.adapters import (
    FixtureAdapter,
    LiveModelUnavailable,
    ModelAdapter,
    OpenAICompatibleAdapter,
)
from .agentcore.policy import Budget
from .baselines import run_lexical, run_single_call
from .corpus import Corpus
from .prompts import PROMPT_VERSION, prompt_hash
from .retrieval import BM25Index
from .schemas import LedgerEntry, LedgerState, Task
from .tools import ALL_TOOLS

ARMS: dict[str, tuple[str, ...] | None] = {
    "lexical": None,
    "single_call": None,
    "agent": ALL_TOOLS,
    "agent_no_expand": tuple(t for t in ALL_TOOLS if t != "expand_context"),
}


# ---------------------------------------------------------------- config


class FamilyPaths(BaseModel):
    corpus: str
    questions: str
    gold: str


class EpisodeSettings(BaseModel):
    max_steps: int = 16
    max_tool_calls: int = 10
    max_tokens_per_episode: int | None = None
    max_wall_seconds: float | None = None
    recent_k: int = 4
    max_completion_tokens: int = 700


class RunCaps(BaseModel):
    max_total_tokens: int | None = None
    max_usd: float | None = None
    usd_per_mtok_input: float | None = None
    usd_per_mtok_output: float | None = None


class EvalConfig(BaseModel):
    """Frozen evaluation settings, loaded from configs/*.yaml."""

    mode: Literal["fixture", "live"]
    model: str | None = None
    families: dict[str, FamilyPaths]
    arms: list[str]
    runs: int = 1
    task_limit: int | None = None
    fixture_scripts: str = "tests/fixtures/scripts"
    episode: EpisodeSettings = Field(default_factory=EpisodeSettings)
    single_call_top_k: int = 4
    single_call_max_completion_tokens: int = 900
    lexical_coverage_threshold: float = 0.5
    run_caps: RunCaps = Field(default_factory=RunCaps)
    adapter_max_retries: int = 2
    adapter_backoff_s: float = 2.0
    output_dir: str = "reports/fixture"
    checkpoint_dir: str = "runs"
    record_timing: bool = True

    def episode_config(self, arm: str) -> EpisodeConfig:
        """Episode settings for an agent arm."""
        allow = ARMS[arm]
        assert allow is not None
        e = self.episode
        return EpisodeConfig(
            budget=Budget(
                max_steps=e.max_steps,
                max_tool_calls=e.max_tool_calls,
                max_tokens=e.max_tokens_per_episode,
                max_wall_seconds=e.max_wall_seconds,
            ),
            allowlist=allow,
            recent_k=e.recent_k,
            record_timing=self.record_timing,
            max_completion_tokens=e.max_completion_tokens,
        )


def load_config(path: Path) -> tuple[EvalConfig, str]:
    """Load a YAML config; return it with the SHA-256 of the file."""
    raw = Path(path).read_bytes()
    cfg = EvalConfig.model_validate(yaml.safe_load(raw))
    unknown = set(cfg.arms) - set(ARMS)
    if unknown:
        raise ValueError(f"unknown arms {sorted(unknown)}")
    return cfg, hashlib.sha256(raw).hexdigest()


def load_tasks(path: Path) -> list[Task]:
    """Questions for one family."""
    return [Task.model_validate(t) for t in json.loads(Path(path).read_text(encoding="utf-8"))]


# ---------------------------------------------------------------- gold


class Anchor(BaseModel):
    doc_id: str
    start: int
    end: int


class GoldTask(BaseModel):
    verdict: str
    abstain_acceptable: bool
    required: list[list[Anchor]]
    acceptable: list[Anchor]
    condition_terms: list[list[str]]


def _resolve_anchor(corpus: Corpus, raw: dict[str, str]) -> Anchor:
    doc = corpus.get(raw["doc_id"])
    if doc is None:
        raise ValueError(f"gold anchor names unknown document {raw['doc_id']}")
    pos = doc.text.find(raw["anchor"])
    if pos < 0 or doc.text.find(raw["anchor"], pos + 1) >= 0:
        raise ValueError(f"gold anchor not found exactly once in {raw['doc_id']}: {raw['anchor']}")
    return Anchor(doc_id=raw["doc_id"], start=pos, end=pos + len(raw["anchor"]))


def load_gold(path: Path, corpus: Corpus) -> dict[str, GoldTask]:
    """Load gold labels and resolve every text anchor to unique offsets."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for task_id, g in data["tasks"].items():
        out[task_id] = GoldTask(
            verdict=g["verdict"],
            abstain_acceptable=g["abstain_acceptable"],
            required=[[_resolve_anchor(corpus, a) for a in grp] for grp in g["required"]],
            acceptable=[_resolve_anchor(corpus, a) for a in g["acceptable"]],
            condition_terms=g["condition_terms"],
        )
    return out


# ---------------------------------------------------------------- scoring


def _overlaps(doc_id: str, start: int, end: int, a: Anchor) -> bool:
    if doc_id != a.doc_id:
        return False
    inter = min(end, a.end) - max(start, a.start)
    return inter > 0 and inter >= 0.5 * min(end - start, a.end - a.start)


def score_entry(entry: LedgerEntry, gold: GoldTask) -> dict[str, Any]:
    """Score one answer against its gold record. See docs/rubric.md."""
    outcome = entry.outcome
    correct = outcome == gold.verdict or (outcome == "abstained" and gold.abstain_acceptable)
    anchors = [a for grp in gold.required for a in grp] + gold.acceptable
    cits = entry.citations
    supporting = (
        [c for c in cits if any(_overlaps(c.doc_id, c.start, c.end, a) for a in anchors)]
        if correct
        else []
    )
    covered = (
        sum(
            any(_overlaps(c.doc_id, c.start, c.end, a) for c in cits for a in grp)
            for grp in gold.required
        )
        if correct
        else 0
    )
    text = (json.dumps(entry.conditions) + " " + entry.claim + " " + entry.rationale).lower()
    terms_found = sum(any(t.lower() in text for t in alts) for alts in gold.condition_terms)
    assertive = outcome in ("supported", "conflicted")
    return {
        "verdict_correct": int(correct),
        "declined": int(outcome in ("abstained", "insufficient")),
        "abstain_expected": int(gold.abstain_acceptable),
        "gold_conflicted": int(gold.verdict == "conflicted"),
        "contradiction_hit": int(
            gold.verdict == "conflicted"
            and outcome == "conflicted"
            and covered == len(gold.required)
        ),
        "accepted_citations": len(cits),
        "supporting_citations": len(supporting),
        "required_groups": len(gold.required),
        "covered_groups": covered,
        "condition_terms": len(gold.condition_terms),
        "condition_terms_found": terms_found,
        "unsupported_claim": int(assertive and (not correct or not supporting)),
        "failed": int(outcome == "failed"),
    }


# ---------------------------------------------------------------- running


def _agent_info(state: LedgerState, cfg: EvalConfig) -> dict[str, Any]:
    attempts = state.finish_attempts
    live = cfg.mode == "live"
    return {
        "model_calls": state.model_calls,
        "tool_calls": cfg.episode.max_tool_calls - state.remaining_tool_calls,
        "steps": state.steps,
        "prompt_chars": state.prompt_chars,
        "prompt_tokens": state.token_usage.prompt if live else None,
        "completion_tokens": state.token_usage.completion if live else None,
        "reported_cost_usd": round(state.reported_cost_usd, 6) if live else None,
        "latency_s": round(state.elapsed_seconds, 3) if cfg.record_timing else None,
        "malformed_actions": state.malformed_actions,
        "reprompts": state.reprompts,
        "citations_emitted": sum(a["citations"] for a in attempts),
        "citations_valid": sum(a["valid_citations"] for a in attempts),
        "quote_mismatches": sum(a["problem_codes"].count("quote_mismatch") for a in attempts),
        "rejected_finishes": sum(not a["accepted"] for a in attempts),
    }


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cost_usd(tokens_in: int, tokens_out: int, caps: RunCaps) -> float | None:
    if caps.usd_per_mtok_input is None or caps.usd_per_mtok_output is None:
        return None
    return (tokens_in * caps.usd_per_mtok_input + tokens_out * caps.usd_per_mtok_output) / 1e6


def run_evaluation(cfg: EvalConfig, cfg_sha: str, root: Path, require_live: bool = False) -> Path:
    """Run every configured arm on every task and write the outputs.

    Args:
        cfg: Loaded configuration.
        cfg_sha: SHA-256 of the config file.
        root: Repository root that relative paths resolve against.
        require_live: Fail unless a live endpoint is configured and used.

    Returns:
        The output directory.

    Raises:
        LiveModelUnavailable: Live mode or ``require_live`` without an endpoint.
    """
    live_adapter: ModelAdapter | None = None
    if cfg.mode == "live":
        live_adapter = OpenAICompatibleAdapter.from_env(
            model=cfg.model, max_retries=cfg.adapter_max_retries, backoff_s=cfg.adapter_backoff_s
        )
    elif require_live:
        raise LiveModelUnavailable("--require-live was given but the config is in fixture mode")
    out = root / cfg.output_dir
    shutil.rmtree(out / "traces", ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    tok_in = tok_out = 0
    reported_usd = 0.0
    fixture_hashes: dict[str, str] = {}
    registries = []

    def adapter_for(family: str, arm: str, task_id: str) -> ModelAdapter:
        if live_adapter is not None:
            return live_adapter
        return FixtureAdapter.from_file(
            root / cfg.fixture_scripts / f"{family}_{arm}.json", task_id
        )

    for family, paths in cfg.families.items():
        corpus = Corpus.load(root / paths.corpus)
        index = BM25Index(corpus)
        tasks = load_tasks(root / paths.questions)[: cfg.task_limit]
        gold = load_gold(root / paths.gold, corpus)
        fixture_hashes |= {
            f"{family}/corpus": corpus.fingerprint(),
            f"{family}/questions": _sha_file(root / paths.questions),
            f"{family}/gold": _sha_file(root / paths.gold),
        }
        if cfg.mode == "fixture":
            for arm in cfg.arms:
                if arm != "lexical":
                    script = root / cfg.fixture_scripts / f"{family}_{arm}.json"
                    fixture_hashes[f"{family}/script/{arm}"] = _sha_file(script)
        for arm in cfg.arms:
            if ARMS[arm] is not None:
                registries.append(make_registry(corpus, cfg.episode_config(arm), index))
        for run in range(cfg.runs):
            for task in tasks:
                for arm in cfg.arms:
                    caps = cfg.run_caps
                    spent = _cost_usd(tok_in, tok_out, caps)
                    if (
                        caps.max_total_tokens is not None
                        and tok_in + tok_out >= caps.max_total_tokens
                    ) or (caps.max_usd is not None and spent is not None and spent >= caps.max_usd):
                        entry = LedgerEntry(
                            task_id=task.task_id,
                            question=task.question,
                            arm=arm,
                            outcome="failed",
                            stop_reason="run_budget_exhausted",
                        )
                        info = {"model_calls": 0, "tool_calls": 0}
                    elif arm == "lexical":
                        entry, info = run_lexical(
                            task, corpus, index, cfg.lexical_coverage_threshold
                        )
                        if not cfg.record_timing:
                            info["latency_s"] = None
                    elif arm == "single_call":
                        entry, info = run_single_call(
                            task,
                            corpus,
                            index,
                            adapter_for(family, arm, task.task_id),
                            cfg.single_call_top_k,
                            cfg.single_call_max_completion_tokens,
                        )
                        if not cfg.record_timing:
                            info["latency_s"] = None
                    else:
                        trace = out / "traces" / family / arm / f"{task.task_id}_run{run}.jsonl"
                        ckpt_dir = root / cfg.checkpoint_dir / cfg.mode / family / arm
                        ckpt = ckpt_dir / f"{task.task_id}_run{run}.ckpt.json"
                        ckpt.unlink(missing_ok=True)
                        entry, state = run_episode(
                            task,
                            corpus,
                            adapter_for(family, arm, task.task_id),
                            cfg.episode_config(arm),
                            arm=arm,
                            run=run,
                            trace_path=trace,
                            checkpoint_path=ckpt,
                            index=index,
                        )
                        info = _agent_info(state, cfg)
                    tok_in += info.get("prompt_tokens") or 0
                    tok_out += info.get("completion_tokens") or 0
                    reported_usd += info.get("reported_cost_usd") or 0.0
                    scores = score_entry(entry, gold[task.task_id])
                    rows.append(
                        {
                            "family": family,
                            "arm": arm,
                            "task_id": task.task_id,
                            "run": run,
                            "mode": cfg.mode,
                            "outcome": entry.outcome,
                            "stop_reason": entry.stop_reason,
                            **scores,
                            **info,
                        }
                    )
                    ledger.append({"family": family, "run": run, **entry.model_dump()})

    model_name = live_adapter.name if live_adapter else "none (scripted fixture adapter)"
    meta = {
        "mode": cfg.mode,
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_dirty": bool(
            _git(root, "status", "--porcelain", "--", "src", "configs", "tests", "evaluator")
        ),
        "package_version": __version__,
        "agentcore_version": AGENTCORE_VERSION,
        "model": model_name,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash(registries),
        "config_sha256": cfg_sha,
        "config": cfg.model_dump(),
        "fixture_hashes": fixture_hashes,
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "python": sys.version.split()[0],
        },
        "tokens": {"prompt": tok_in, "completion": tok_out} if cfg.mode == "live" else None,
        "usd": _cost_usd(tok_in, tok_out, cfg.run_caps) if cfg.mode == "live" else None,
        "usd_reported_by_provider": round(reported_usd, 6) if cfg.mode == "live" else None,
        "adapter_retries": getattr(live_adapter, "retries", None),
    }
    write_outputs(out, rows, ledger, meta)
    return out


# ---------------------------------------------------------------- aggregation

RATES = [
    ("verdict_accuracy", "verdict_correct", None),
    ("citation_validity", "citations_valid", "citations_emitted"),
    ("support_precision", "supporting_citations", "accepted_citations"),
    ("support_recall", "covered_groups", "required_groups"),
    ("contradiction_recall", "contradiction_hit", "gold_conflicted"),
    ("correct_abstention", None, "abstain_expected"),
    ("condition_recall", "condition_terms_found", "condition_terms"),
]


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One comparison row per (family, arm) with numerators and denominators."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["family"], r["arm"]), []).append(r)
    out = []
    for (family, arm), rs in groups.items():
        row: dict[str, Any] = {
            "family": family,
            "arm": arm,
            "mode": rs[0]["mode"],
            "episodes": len(rs),
            "runs": len({r["run"] for r in rs}),
        }
        for name, num, den in RATES:
            if name == "correct_abstention":
                k = sum(r["declined"] for r in rs if r["abstain_expected"])
                n = sum(r["abstain_expected"] for r in rs)
            else:
                k = sum(r.get(num, 0) or 0 for r in rs)
                n = len(rs) if den is None else sum(r.get(den, 0) or 0 for r in rs)
            row[f"{name}_k"], row[f"{name}_n"] = k, n
            row[name] = round(k / n, 3) if n else None
        emitted = sum(r.get("citations_emitted", 0) or 0 for r in rs)
        mism = sum(r.get("quote_mismatches", 0) or 0 for r in rs)
        row["quote_fidelity_k"], row["quote_fidelity_n"] = emitted - mism, emitted
        row["quote_fidelity"] = round((emitted - mism) / emitted, 3) if emitted else None
        row["unsupported_claims"] = sum(r["unsupported_claim"] for r in rs)
        row["failures"] = sum(r["failed"] for r in rs)
        row["malformed_actions"] = sum(r.get("malformed_actions", 0) or 0 for r in rs)
        row["reprompts"] = sum(r.get("reprompts", 0) or 0 for r in rs)
        row["rejected_finishes"] = sum(r.get("rejected_finishes", 0) or 0 for r in rs)
        row["tool_calls_total"] = sum(r.get("tool_calls", 0) or 0 for r in rs)
        row["model_calls_total"] = sum(r.get("model_calls", 0) or 0 for r in rs)
        row["prompt_chars_total"] = sum(r.get("prompt_chars", 0) or 0 for r in rs)
        toks = [r.get("prompt_tokens") for r in rs]
        row["tokens_total"] = (
            None
            if all(t is None for t in toks)
            else sum((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in rs)
        )
        costs = [r.get("reported_cost_usd") for r in rs]
        row["reported_cost_usd_total"] = (
            None if all(c is None for c in costs) else round(sum(c or 0.0 for c in costs), 6)
        )
        lat = [r.get("latency_s") for r in rs if r.get("latency_s") is not None]
        row["latency_s_mean"] = round(sum(lat) / len(lat), 3) if lat else None
        per_run = {}
        for r in rs:
            per_run.setdefault(r["run"], []).append(r["verdict_correct"])
        accs = [sum(v) / len(v) for v in per_run.values()]
        row["verdict_accuracy_min_run"] = round(min(accs), 3)
        row["verdict_accuracy_max_run"] = round(max(accs), 3)
        out.append(row)
    return out


def write_outputs(out: Path, rows: list[dict], ledger: list[dict], meta: dict) -> None:
    """Write task_results.jsonl, ledger.json, comparison.csv and run_meta.json."""
    with (out / "task_results.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    (out / "ledger.json").write_text(
        json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    comparison = aggregate(rows)
    with (out / "comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(comparison[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(comparison)
    (out / "run_meta.json").write_text(
        json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
