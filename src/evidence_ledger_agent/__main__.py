"""Command line: demo, evaluate, report and verify."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .agent import EpisodeConfig, run_episode
from .agentcore.adapters import FixtureAdapter, LiveModelUnavailable, OpenAICompatibleAdapter
from .citation_checks import audit_entry
from .corpus import Corpus
from .evaluation import load_config, load_tasks, run_evaluation
from .report import write_reports
from .schemas import LedgerEntry, LedgerState

ROOT = Path.cwd()
FIX = Path("tests/fixtures")
DEMO_TASKS = ("dev-q1", "dev-q5")


def _short(obj: object, n: int = 70) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 3] + "..."


def _steps_table(state: LedgerState) -> Table:
    t = Table(title=f"{state.task_id}: steps", show_lines=False)
    for col in ("#", "tool", "arguments", "result", "model summary"):
        t.add_column(col, overflow="fold")
    for h in state.history:
        args = {k: v for k, v in h.action.arguments.items() if k not in ("rationale", "claim")}
        if h.result.ok:
            out = h.result.output or {}
            res = (
                f"{len(out['hits'])} hits: " + ", ".join(x["doc_id"] for x in out["hits"])
                if "hits" in out
                else out.get("span_id", out.get("verdict", "ok"))
            )
        else:
            res = f"REJECTED {h.result.error.code}: {_short(h.result.error.message, 60)}"
        t.add_row(str(h.step), h.action.tool, _short(args, 60), res, _short(h.summary, 50))
    return t


def _ledger_table(entries: list[LedgerEntry]) -> Table:
    t = Table(title="Evidence ledger", show_lines=True)
    for col in ("task", "outcome", "claim / reason", "citation", "doc hash", "verbatim quote"):
        t.add_column(col, overflow="fold")
    for e in entries:
        text = e.claim or e.abstain_reason or ""
        if e.conditions:
            text += "\nconditions: " + "; ".join(f"{k}: {v}" for k, v in e.conditions.items())
        if not e.citations:
            t.add_row(e.task_id, e.outcome, text, "none", "", "")
        for i, c in enumerate(e.citations):
            t.add_row(
                e.task_id if i == 0 else "",
                e.outcome if i == 0 else "",
                text if i == 0 else "",
                f"{c.doc_id} [{c.start}:{c.end}]",
                c.doc_hash[:12],
                c.quote,
            )
    return t


def run_demo(mode: str, root: Path, console: Console | None = None) -> list[LedgerEntry]:
    """Audit the pH question and the unanswerable question; return the ledger."""
    corpus = Corpus.load(root / FIX / "corpus" / "dev")
    tasks = {t.task_id: t for t in load_tasks(root / FIX / "questions_dev.json")}
    live = OpenAICompatibleAdapter.from_env() if mode == "live" else None
    entries = []
    for task_id in DEMO_TASKS:
        adapter = live or FixtureAdapter.from_file(
            root / FIX / "scripts" / "dev_agent.json", task_id
        )
        entry, state = run_episode(
            tasks[task_id], corpus, adapter, EpisodeConfig(record_timing=False)
        )
        entries.append(entry)
        if console:
            console.print(f"\n[bold]{tasks[task_id].question}[/bold]")
            console.print(_steps_table(state))
    if console:
        console.print(_ledger_table(entries))
        label = "scripted fixture adapter, no model" if mode == "fixture" else live.name
        console.print(
            f"Mode: {mode} ({label}). Every quote above was checked character for "
            "character against the hashed document text."
        )
    return entries


def verify_ledger(path: Path, root: Path) -> list[str]:
    """Re-audit every citation in a saved ledger against the hashed corpora."""
    corpora = {f: Corpus.load(root / FIX / "corpus" / f) for f in ("dev", "heldout")}
    problems = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        family = item.pop("family")
        item.pop("run", None)
        problems += audit_entry(corpora[family], LedgerEntry.model_validate(item))
    return problems


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m evidence_ledger_agent``."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="evidence_ledger_agent", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("demo", help="run the two demo questions and print the ledger")
    p.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    p.add_argument("--save", type=Path, help="write the ledger as JSON")
    p = sub.add_parser("evaluate", help="run all arms on all tasks of a config")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument(
        "--require-live",
        action="store_true",
        help="fail unless a live model endpoint is configured",
    )
    p = sub.add_parser("report", help="regenerate evidence files from saved outputs")
    p.add_argument("--update-readme", action="store_true")
    p = sub.add_parser("verify", help="re-audit every citation in a saved ledger")
    p.add_argument("--ledger", type=Path, default=Path("reports/fixture/ledger.json"))
    args = parser.parse_args(argv)
    console = Console(width=160)
    try:
        if args.cmd == "demo":
            entries = run_demo(args.mode, ROOT, console)
            if args.save:
                args.save.write_text(
                    json.dumps([e.model_dump() for e in entries], indent=1, ensure_ascii=False)
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
        elif args.cmd == "evaluate":
            cfg, sha = load_config(args.config)
            if args.require_live and cfg.mode != "live":
                raise LiveModelUnavailable("--require-live needs a config with mode: live")
            out = run_evaluation(cfg, sha, ROOT, require_live=args.require_live)
            console.print(
                f"wrote {out.relative_to(ROOT)}/ (ledger.json, task_results.jsonl, "
                "comparison.csv, run_meta.json, traces/)"
            )
        elif args.cmd == "report":
            ev = write_reports(ROOT, update_readme=args.update_readme)
            console.print(
                "wrote reports/evidence.json and reports/evidence.md; modes: "
                + ", ".join(
                    f"{k}={'pending' if v == 'pending' else 'saved'}"
                    for k, v in ev["modes"].items()
                )
            )
        elif args.cmd == "verify":
            problems = verify_ledger(args.ledger, ROOT)
            n = len(json.loads(args.ledger.read_text(encoding="utf-8")))
            if problems:
                console.print("\n".join(problems))
                return 1
            console.print(f"all citations in {n} ledger entries verified against the corpus")
    except LiveModelUnavailable as exc:
        console.print(f"[red]live model unavailable:[/red] {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
