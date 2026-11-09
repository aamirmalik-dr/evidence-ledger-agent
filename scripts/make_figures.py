"""Draw the README figures from saved run outputs only.

Reads reports/live, reports/live_v2 and reports/live_v2_sonnet
(task_results.jsonl) and writes PNGs to docs/figures/. No model is called and
nothing is estimated; running it twice gives identical files.

Usage: python scripts/make_figures.py [--out docs/figures]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_style as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = [
    ("live", "v1 · gpt-4.1-mini\nheld-out v1 · 10 q x 2 runs", False),
    ("live_v2", "v2 · gpt-4.1-mini\nheldout_v2 · 10 q x 2 runs", False),
    ("live_v2_sonnet", "v2 · claude-sonnet-4.6\nheldout_v2 · 10 q x 1 run", True),
]
ARMS = ["lexical", "single_call", "agent", "agent_no_expand"]
ARM_TYPE = {
    "lexical": "baseline",
    "single_call": "single",
    "agent": "agent",
    "agent_no_expand": "ablation",
}
ARM_LABEL = {
    "lexical": "lexical\n(no model)",
    "single_call": "single\ncall",
    "agent": "agent",
    "agent_no_expand": "agent, no\nexpand",
}
FIGURES = [
    "accuracy_by_arm.png",
    "failure_breakdown.png",
    "v2_question_outcomes.png",
    "tool_calls_per_episode.png",
]


def load(name: str) -> list[dict]:
    path = ROOT / "reports" / name / "task_results.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r["arm"]].append(r)
    return out


def accuracy_by_arm(out: Path) -> None:
    fig, ax = plt.subplots(figsize=(fs.WIDTH, 4.8))
    x, ticks, labels, group_mid = 0.0, [], [], []
    for name, title, second in ROUNDS:
        arms = by_arm(load(name))
        start = x
        for arm in ARMS:
            if arm not in arms:
                continue
            rs = arms[arm]
            k, n = sum(r["verdict_correct"] for r in rs), len(rs)
            ax.bar(x, k / n, width=0.7, **fs.bar_kwargs(ARM_TYPE[arm], second))
            runs = sorted({r["run"] for r in rs})
            per_run = [
                sum(r["verdict_correct"] for r in rs if r["run"] == i)
                / sum(1 for r in rs if r["run"] == i)
                for i in runs
            ]
            if len(per_run) > 1:
                fs.points(ax, x, per_run)
            top = max([k / n, *per_run])
            ax.text(x, top + 0.03, f"{k}/{n}", ha="center", va="bottom", fontsize=10)
            ticks.append(x)
            labels.append(ARM_LABEL[arm])
            x += 1
        group_mid.append(((start + x - 1) / 2, title))
        x += 0.8
    ax.set_xticks(ticks, labels)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_ylabel("Verdict accuracy")
    for mid, title in group_mid:
        ax.text(mid, -0.36, title, ha="center", va="top", fontsize=10, transform=ax.transData)
    ax.set_title(
        "Verdict accuracy by arm, live runs on held-out questions\n"
        "bars: all episodes; points: individual runs; hatched: second model",
        loc="left",
    )
    fig.subplots_adjust(left=0.08, right=0.99, top=0.85, bottom=0.30)
    fs.save(fig, out / "accuracy_by_arm.png")


def classify(r: dict) -> str:
    if r["outcome"] == "failed":
        return "budget stop"
    if not r["verdict_correct"]:
        return "wrong verdict"
    if r["unsupported_claim"]:
        return "right verdict, unsupported claim"
    return "right verdict, supported"


CATEGORIES = [
    ("right verdict, supported", fs.OUTCOME["correct"]),
    ("right verdict, unsupported claim", fs.OUTCOME["abstained"]),
    ("wrong verdict", fs.OUTCOME["wrong"]),
    ("budget stop", fs.OUTCOME["failed"]),
]


def failure_breakdown(out: Path) -> None:
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(fs.WIDTH, 5.0), gridspec_kw={"width_ratios": [1, 1.6]}
    )
    llm_arms = ["single_call", "agent", "agent_no_expand"]
    rounds = [("live", "v1"), ("live_v2", "v2")]
    data = {name: by_arm(load(name)) for name, _ in rounds}
    pos, labels = [], []
    x = 0.0
    for arm in llm_arms:
        for name, tag in rounds:
            pos.append((x, arm, name, tag))
            labels.append(f"{tag}")
            x += 1
        x += 0.6
    for xi, arm, name, _ in pos:
        m = sum(r["malformed_actions"] for r in data[name][arm])
        left.bar(xi, m, width=0.8, **fs.bar_kwargs(ARM_TYPE[arm]))
        left.text(xi, m + 0.3, str(m), ha="center", va="bottom", fontsize=10)
    left.set_xticks([p[0] for p in pos], labels)
    for i, arm in enumerate(llm_arms):
        left.text(
            (pos[2 * i][0] + pos[2 * i + 1][0]) / 2,
            -0.13,
            ARM_LABEL[arm].replace("\n", " "),
            ha="center",
            va="top",
            transform=left.get_xaxis_transform(),
            fontsize=10,
        )
    left.set_ylabel("Malformed replies (steps)")
    left.set_title("Malformed replies rejected\nby the parser", loc="left")
    left.set_ylim(0, 19)
    left.yaxis.set_major_locator(MaxNLocator(integer=True))

    arms = ["lexical", "single_call", "agent", "agent_no_expand"]
    pos2, labels2 = [], []
    x = 0.0
    for arm in arms:
        for name, tag in rounds:
            pos2.append((x, arm, name))
            labels2.append(tag)
            x += 1
        x += 0.6
    for xi, arm, name in pos2:
        rs = data[name][arm]
        bottom = 0
        for cat, colour in CATEGORIES:
            c = sum(classify(r) == cat for r in rs)
            if c:
                right.bar(
                    xi, c, width=0.8, bottom=bottom, color=colour, edgecolor=fs.EDGE, linewidth=0.8
                )
                if c >= 1:
                    right.text(
                        xi,
                        bottom + c / 2,
                        str(c),
                        ha="center",
                        va="center",
                        fontsize=10,
                        color="white" if colour in (fs.OUTCOME["failed"],) else fs.TEXT,
                    )
            bottom += c
    right.set_xticks([p[0] for p in pos2], labels2)
    for i, arm in enumerate(arms):
        right.text(
            (pos2[2 * i][0] + pos2[2 * i + 1][0]) / 2,
            -0.13,
            ARM_LABEL[arm].replace("\n", " "),
            ha="center",
            va="top",
            transform=right.get_xaxis_transform(),
            fontsize=10,
        )
    right.set_ylabel("Episodes (of 20)")
    right.set_ylim(0, 21)
    right.yaxis.set_major_locator(MaxNLocator(integer=True))
    right.set_title("Episode outcomes", loc="left")
    right.legend(
        handles=[Patch(facecolor=c, edgecolor=fs.EDGE, label=k) for k, c in CATEGORIES],
        loc="upper center",
        bbox_to_anchor=(0.45, -0.2),
        ncol=2,
        frameon=False,
    )
    fig.suptitle(
        "Live, gpt-4.1-mini, v1 held-out v1 and v2 heldout_v2, 10 questions x 2 runs per arm",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    fig.subplots_adjust(left=0.07, right=0.99, top=0.82, bottom=0.30, wspace=0.25)
    fs.save(fig, out / "failure_breakdown.png")


def cell_outcome(r: dict) -> str:
    if r["outcome"] == "failed":
        return "failed"
    if r["verdict_correct"]:
        return "correct"
    if r["outcome"] == "abstained":
        return "abstained"
    return "wrong"


def question_outcomes(out: Path) -> None:
    cols = []
    for name, model in (("live_v2", "mini"), ("live_v2_sonnet", "sonnet")):
        arms = by_arm(load(name))
        for arm in ARMS:
            for run in sorted({r["run"] for r in arms.get(arm, [])}):
                rs = {r["task_id"]: r for r in arms[arm] if r["run"] == run}
                cols.append((f"{ARM_LABEL[arm].replace(chr(10), ' ')}\n{model} r{run}", rs))
    qs = sorted({q for _, rs in cols for q in rs})
    codes = {"correct": "C", "wrong": "W", "abstained": "A", "failed": "F"}
    fig, ax = plt.subplots(figsize=(10, 5.8))
    for j, (_, rs) in enumerate(cols):
        for i, q in enumerate(qs):
            o = cell_outcome(rs[q])
            ax.add_patch(
                plt.Rectangle(
                    (j, i), 1, 1, facecolor=fs.OUTCOME[o], edgecolor="white", linewidth=1.5
                )
            )
            ax.text(
                j + 0.5,
                i + 0.5,
                codes[o],
                ha="center",
                va="center",
                fontsize=10,
                color="white" if o in ("failed", "wrong", "correct") else fs.TEXT,
            )
    ax.set_xlim(0, len(cols))
    ax.set_ylim(len(qs), 0)
    ax.set_xticks([j + 0.5 for j in range(len(cols))], [c[0] for c in cols], fontsize=10)
    ax.set_yticks([i + 0.5 for i in range(len(qs))], qs)
    ax.tick_params(axis="x", rotation=90)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.axvline(8, color=fs.EDGE, linewidth=1.5)
    ax.legend(
        handles=[
            Patch(facecolor=fs.OUTCOME["correct"], label="C correct (incl. correct abstention)"),
            Patch(facecolor=fs.OUTCOME["wrong"], label="W wrong verdict"),
            Patch(facecolor=fs.OUTCOME["abstained"], label="A abstained, answer expected"),
            Patch(facecolor=fs.OUTCOME["failed"], label="F failed (budget stop)"),
        ],
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
    )
    ax.set_title(
        "Per-question outcomes, live, heldout_v2 (10 questions)\n"
        "left of the line: gpt-4.1-mini, 2 runs; right: claude-sonnet-4.6, 1 run",
        loc="left",
    )
    fig.subplots_adjust(left=0.08, right=0.64, top=0.88, bottom=0.30)
    fs.save(fig, out / "v2_question_outcomes.png")


def tool_calls(out: Path) -> None:
    groups = []
    for name, title, second in ROUNDS:
        arms = by_arm(load(name))
        for arm in ("agent", "agent_no_expand"):
            if arm in arms:
                short = title.split("\n")[0]
                groups.append(
                    (f"{ARM_LABEL[arm].replace(chr(10), ' ')}\n{short}", arm, second, arms[arm])
                )
    fig, ax = plt.subplots(figsize=(fs.WIDTH, 4.8))
    for x, (_, arm, second, rs) in enumerate(groups):
        vals = sorted(r["tool_calls"] for r in rs)
        seen: dict[int, int] = defaultdict(int)
        for v in vals:
            seen[v] += 1
        placed: dict[int, int] = defaultdict(int)
        for v in vals:
            m = seen[v]
            off = (placed[v] - (m - 1) / 2) * 0.07
            placed[v] += 1
            colour = fs.arm_colour(fs_type(arm))
            ax.scatter(
                x + off,
                v,
                s=30,
                color="white" if second else colour,
                edgecolor=colour if second else fs.EDGE,
                linewidth=1.8 if second else 0.8,
                zorder=3,
            )
        med = (
            sorted(vals)[len(vals) // 2]
            if len(vals) % 2
            else sum(sorted(vals)[len(vals) // 2 - 1 : len(vals) // 2 + 1]) / 2
        )
        ax.plot([x - 0.35, x + 0.35], [med, med], color=fs.EDGE, linewidth=2, zorder=4)
        ax.text(x + 0.38, med, f"median {med:g}\nn={len(vals)}", va="center", fontsize=10)
    ax.axhline(10, color=fs.MUTED, linestyle="--", linewidth=1)
    ax.text(len(groups) - 0.5, 10.2, "tool-call cap (10)", ha="right", fontsize=10, color=fs.MUTED)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups])
    ax.set_xlim(-0.6, len(groups) - 0.1)
    ax.set_ylim(0, 11.5)
    ax.set_ylabel("Tool calls per episode")
    ax.set_title(
        "Tool calls per episode, agent arms, live held-out runs\n"
        "points: episodes; line: median; outlined points: second model",
        loc="left",
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.85, bottom=0.22)
    fs.save(fig, out / "tool_calls_per_episode.png")


def fs_type(arm: str) -> str:
    return ARM_TYPE[arm]


def main(argv: list[str] | None = None) -> list[Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "figures")
    args = parser.parse_args(argv)
    fs.apply()
    args.out.mkdir(parents=True, exist_ok=True)
    accuracy_by_arm(args.out)
    failure_breakdown(args.out)
    question_outcomes(args.out)
    tool_calls(args.out)
    return [args.out / f for f in FIGURES]


if __name__ == "__main__":
    for p in main():
        print(f"wrote {p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p}")
