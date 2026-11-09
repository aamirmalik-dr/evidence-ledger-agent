"""Build reports/evidence.json, reports/evidence.md and the README table.

Everything here is read from saved run outputs (run_meta.json,
comparison.csv, task_results.jsonl). Nothing is estimated; a mode without
saved outputs is reported as "pending".
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

MODES = ("fixture", "live")
README_START, README_END = "<!-- evidence-table:start -->", "<!-- evidence-table:end -->"
SCRIPTED_NOTE = (
    "Fixture mode replays hand-written scripted replies for the single_call, agent and "
    "agent_no_expand arms, including deliberately planted failures. Those rows validate the "
    "loop, policy and scorer; they are not measurements of any model. The lexical arm uses no "
    "model, so its fixture rows are genuine measurements of that baseline on this corpus."
)
LIMITATIONS = [
    "The corpus is small (24 fictional documents, 16 questions) and written by the author; "
    "it is a test bed, not a benchmark.",
    "Citation checks prove quote identity and provenance, not scientific support; support is "
    "scored against hand-written gold spans with a 50 percent overlap rule.",
    "Condition recall is a substring check over the answer's conditions, claim and rationale.",
    "Fixture results for model arms are scripted and carry no information about model quality.",
    "No live model has been evaluated yet; live results are pending.",
]


def _num(v: str) -> Any:
    if v == "":
        return None
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() and "." not in v else f


def load_mode(reports: Path, mode: str) -> dict[str, Any] | None:
    """Saved outputs for one mode, or None if that mode has never run."""
    d = reports / mode
    if not (d / "run_meta.json").exists():
        return None
    meta = json.loads((d / "run_meta.json").read_text(encoding="utf-8"))
    with (d / "comparison.csv").open(encoding="utf-8") as fh:
        comparison = [{k: _num(v) for k, v in row.items()} for row in csv.DictReader(fh)]
    rows = [
        json.loads(line)
        for line in (d / "task_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    failures = [
        {k: r[k] for k in ("family", "arm", "task_id", "run", "outcome", "stop_reason")}
        | {
            "verdict_correct": r["verdict_correct"],
            "rejected_finishes": r.get("rejected_finishes"),
            "malformed_actions": r.get("malformed_actions"),
            "reprompts": r.get("reprompts"),
            "invalid_citations": (r.get("citations_emitted") or 0)
            - (r.get("citations_valid") or 0),
        }
        for r in rows
        if r["outcome"] == "failed"
        or not r["verdict_correct"]
        or r.get("rejected_finishes")
        or r.get("malformed_actions")
        or r.get("reprompts")
        or (r.get("citations_emitted") or 0) != (r.get("citations_valid") or 0)
    ]
    return {"meta": meta, "metrics": comparison, "failures": failures, "n_rows": len(rows)}


def build_evidence(root: Path) -> dict[str, Any]:
    """Assemble the evidence record from saved outputs."""
    reports = root / "reports"
    evidence: dict[str, Any] = {"schema": "evidence-v1", "modes": {}}
    for mode in MODES:
        data = load_mode(reports, mode)
        if data is None:
            evidence["modes"][mode] = "pending"
            continue
        m = data["meta"]
        evidence["modes"][mode] = {
            "mode": mode,
            "interpretation": SCRIPTED_NOTE if mode == "fixture" else "live model results",
            "git_commit": m["git_commit"],
            "git_dirty": m["git_dirty"],
            "model": m["model"],
            "prompt_version": m["prompt_version"],
            "prompt_sha256": m["prompt_sha256"],
            "config_sha256": m["config_sha256"],
            "fixture_hashes": m["fixture_hashes"],
            "hardware": m["hardware"],
            "started_at": m["started_at"],
            "finished_at": m["finished_at"],
            "caps": {"episode": m["config"]["episode"], "run": m["config"]["run_caps"]},
            "cost": {"tokens": m["tokens"], "usd": m["usd"]},
            "metrics": data["metrics"],
            "failures": data["failures"],
            "episodes": data["n_rows"],
        }
    evidence["limitations"] = LIMITATIONS
    evidence["reproduce"] = {
        "fixture": "python -m evidence_ledger_agent evaluate --config configs/fixture.yaml "
        "&& python -m evidence_ledger_agent report --update-readme",
        "live": "python -m evidence_ledger_agent evaluate --config configs/live.yaml "
        "--require-live && python -m evidence_ledger_agent report --update-readme",
        "audit": "python -m evidence_ledger_agent verify",
    }
    return evidence


def _frac(row: dict[str, Any], name: str) -> str:
    k, n = row.get(f"{name}_k"), row.get(f"{name}_n")
    if not n:
        return "n/a"
    return f"{row[name]:.2f} ({k}/{n})"


def _label(mode: str, arm: str) -> str:
    if mode == "fixture":
        return "fixture, deterministic" if arm == "lexical" else "fixture, scripted"
    return "live"


def metrics_table(evidence: dict[str, Any]) -> str:
    """Markdown table of every measured row, with the mode in every row."""
    head = (
        "| Mode | Family | Arm | Verdict accuracy | Citation validity | Support precision "
        "| Support recall | Contradiction recall | Correct abstention | Unsupported claims "
        "| Failures | Tool calls | Model calls |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for mode in MODES:
        data = evidence["modes"][mode]
        if data == "pending":
            lines.append(f"| {mode}: pending | | | | | | | | | | | | |")
            continue
        for r in data["metrics"]:
            lines.append(
                f"| {_label(mode, r['arm'])} | {r['family']} | {r['arm']} "
                f"| {_frac(r, 'verdict_accuracy')} | {_frac(r, 'citation_validity')} "
                f"| {_frac(r, 'support_precision')} | {_frac(r, 'support_recall')} "
                f"| {_frac(r, 'contradiction_recall')} | {_frac(r, 'correct_abstention')} "
                f"| {r['unsupported_claims']} | {r['failures']} | {r['tool_calls_total']} "
                f"| {r['model_calls_total']} |"
            )
    return head + "\n".join(lines) + "\n"


def evidence_markdown(evidence: dict[str, Any]) -> str:
    """Human-readable evidence report."""
    out = [
        "# Evidence",
        "",
        "Generated from saved run outputs by "
        "`python -m evidence_ledger_agent report`. Do not edit by hand.",
        "",
    ]
    for mode in MODES:
        data = evidence["modes"][mode]
        out += [f"## {mode.capitalize()} mode", ""]
        if data == "pending":
            out += ["Pending. No saved outputs exist for this mode.", ""]
            continue
        out += [
            data["interpretation"],
            "",
            f"- Commit: `{data['git_commit']}` (working tree dirty: {data['git_dirty']})",
            f"- Model: {data['model']}",
            f"- Prompt: {data['prompt_version']}, sha256 `{data['prompt_sha256'][:16]}`",
            f"- Config sha256: `{data['config_sha256'][:16]}`",
            f"- Run: {data['started_at']} to {data['finished_at']}",
            f"- Hardware: {data['hardware']['platform']}, Python {data['hardware']['python']}",
            f"- Episodes scored: {data['episodes']}",
            f"- Tokens: {data['cost']['tokens']}, USD: {data['cost']['usd']}",
            "",
            "### Fixture hashes",
            "",
        ]
        out += [f"- {k}: `{v[:16]}`" for k, v in sorted(data["fixture_hashes"].items())]
        out += [
            "",
            "### Every failed, wrong or repaired episode",
            "",
            "| Family | Arm | Task | Run | Outcome | Stop reason | Correct | Rejected finishes "
            "| Malformed | Re-prompts | Invalid citations |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        out += [
            f"| {f['family']} | {f['arm']} | {f['task_id']} | {f['run']} | {f['outcome']} "
            f"| {f['stop_reason']} | {f['verdict_correct']} | {f['rejected_finishes']} "
            f"| {f['malformed_actions']} | {f['reprompts']} | {f['invalid_citations']} |"
            for f in data["failures"]
        ]
        out.append("")
    out += ["## Metrics", "", metrics_table(evidence), "## Limitations", ""]
    out += [f"- {x}" for x in evidence["limitations"]]
    out += ["", "## Reproduce", ""]
    out += [f"- {k}: `{v}`" for k, v in evidence["reproduce"].items()]
    return "\n".join(out) + "\n"


def write_reports(root: Path, update_readme: bool = False) -> dict[str, Any]:
    """Write evidence.json and evidence.md; optionally refresh the README table."""
    evidence = build_evidence(root)
    reports = root / "reports"
    (reports / "evidence.json").write_text(
        json.dumps(evidence, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    (reports / "evidence.md").write_text(
        evidence_markdown(evidence), encoding="utf-8", newline="\n"
    )
    if update_readme:
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(README_START) + ".*?" + re.escape(README_END), re.S)
        if not pattern.search(text):
            raise ValueError("README has no evidence-table markers")
        block = f"{README_START}\n{metrics_table(evidence)}{README_END}"
        readme.write_text(pattern.sub(lambda _: block, text), encoding="utf-8", newline="\n")
    return evidence
