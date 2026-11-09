"""Draw the README figures from saved run outputs only.

Reads reports/live, reports/live_v2 and reports/live_v2_sonnet
(task_results.jsonl) and writes each figure to docs/figures/ as SVG and as a
300 dpi PNG. No model is called and nothing is estimated; the intervals are
computed from the saved per-episode rows (see figure_style.py). Running the
script twice gives byte-identical files.

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
import numpy as np  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# (report folder, label, second model)
CONDITIONS = [
    ("live", "v1, gpt-4.1-mini", False),
    ("live_v2", "v2, gpt-4.1-mini", False),
    ("live_v2_sonnet", "v2, claude-sonnet-4.6", True),
]
ARMS = ["lexical", "single_call", "agent", "agent_no_expand"]
ARM_TYPE = {
    "lexical": "baseline",
    "single_call": "single",
    "agent": "agent",
    "agent_no_expand": "ablation",
}
ARM_NAME = {
    "lexical": "Lexical (no model)",
    "single_call": "Single call",
    "agent": "Agent",
    "agent_no_expand": "Agent, no expand",
}
STEMS = ["fig1_main", "figS1_tool_calls", "figS2_citation_vs_accuracy"]
# Every plotted interval, written to docs/figures/figure_stats.json for the captions.
STATS: dict[str, dict] = {}
# Episode outcome classes, in plotting order.
CLASSES = [
    ("correct", "Right verdict, supported, or correct abstention", "C"),
    ("partial", "Right verdict, unsupported claim", "U"),
    ("abstained", "Abstained, answer expected", "A"),
    ("wrong", "Wrong verdict", "W"),
    ("failed", "Budget stop (tool-call or token cap)", "F"),
]


def load(name: str) -> list[dict]:
    path = ROOT / "reports" / name / "task_results.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r["arm"]].append(r)
    return out


def classify(r: dict) -> str:
    """One outcome class per episode, checked in this order."""
    if r["outcome"] == "failed":
        return "failed"
    if r["verdict_correct"]:
        return "partial" if r["unsupported_claim"] else "correct"
    if r["outcome"] == "abstained":
        return "abstained"
    return "wrong"


def per_task(rows: list[dict], key: str) -> dict[str, float]:
    """Mean of a 0/1 field per task, averaged over that task's runs."""
    acc: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        acc[r["task_id"]].append(float(r[key]))
    return {t: float(np.mean(v)) for t, v in acc.items()}


def paired(rows_a: list[dict], rows_b: list[dict], key: str) -> tuple[float, float, float, int]:
    a, b = per_task(rows_a, key), per_task(rows_b, key)
    tasks = sorted(set(a) & set(b))
    m, lo, hi = fs.paired_bootstrap([a[t] for t in tasks], [b[t] for t in tasks])
    return m, lo, hi, len(tasks)


def rate(rows: list[dict], key: str) -> tuple[float, float, float, int, int]:
    k, n = sum(int(r[key]) for r in rows), len(rows)
    p, lo, hi = fs.wilson(k, n)
    return p, lo, hi, k, n


# Figure 1 -------------------------------------------------------------------


def panel_accuracy(fig, data, top: float) -> None:
    left0, width, gap, height = 27.0, 24.0, 4.0, 40.0
    ys = {arm: i for i, arm in enumerate(ARMS)}
    for j, (name, label, second) in enumerate(CONDITIONS):
        ax = fs.axes_mm(fig, left0 + j * (width + gap), top, width, height)
        arms = data[name]
        for arm in ARMS:
            if arm not in arms:
                ax.text(0.5, ys[arm], "not run", ha="center", va="center", color=fs.MUTED)
                continue
            p, lo, hi, k, n = rate(arms[arm], "verdict_correct")
            STATS[f"accuracy/{name}/{arm}"] = {"k": k, "n": n, "rate": p, "wilson95": [lo, hi]}
            fs.dot_interval(ax, ys[arm], p, lo, hi, ARM_TYPE[arm], second)
            ax.text(0.0, ys[arm] - 0.34, f"{k}/{n}", color=fs.MUTED, va="center", ha="left")
        ax.set_xlim(-0.03, 1.03)
        ax.spines["bottom"].set_bounds(0, 1)
        ax.set_ylim(len(ARMS) - 0.5, -0.6)
        ax.xaxis.set_major_locator(MultipleLocator(0.5))
        ax.xaxis.set_minor_locator(MultipleLocator(0.1))
        ax.set_xticks([0, 0.5, 1])
        fs.tidy_ticks(ax, "x")
        ax.set_yticks(range(len(ARMS)))
        if j == 0:
            ax.set_yticklabels([ARM_NAME[a] for a in ARMS])
        else:
            ax.set_yticklabels([])
            ax.tick_params(axis="y", length=0)
            ax.spines["left"].set_visible(False)
        head, model = label.split(", ")
        ax.set_title(f"{head}\n{model}", loc="center")
        if j == 1:
            ax.set_xlabel("Verdict accuracy (fraction)")
    fs.panel_label(fig, "a", 1.5, top - 6.5)


def panel_forest(fig, data, top: float) -> None:
    left, width, height = 137.0, 40.0, 40.0
    ax = fs.axes_mm(fig, left, top, width, height)
    rows = []
    for name, label, second in CONDITIONS:
        for arm in ("agent", "agent_no_expand"):
            if arm in data[name]:
                m, lo, hi, n = paired(data[name][arm], data[name]["single_call"], "verdict_correct")
                STATS[f"paired_vs_single_call/{name}/{arm}"] = {
                    "mean_difference": m,
                    "bootstrap95": [lo, hi],
                    "n_tasks": n,
                }
                rows.append((f"{ARM_NAME[arm]}\n{label}", arm, second, m, lo, hi, n))
    for i, (_, arm, second, m, lo, hi, _n) in enumerate(rows):
        fs.dot_interval(ax, i, m, lo, hi, ARM_TYPE[arm], second)
    fs.ref_line(ax, 0.0, "x")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set_ylim(len(rows) - 0.5, -1.0)
    ax.set_xlim(-0.6, 0.25)
    ax.spines["bottom"].set_bounds(-0.6, 0.2)
    ax.set_xticks([-0.6, -0.4, -0.2, 0, 0.2])
    fs.tidy_ticks(ax, "x")
    ax.xaxis.set_minor_locator(MultipleLocator(0.1))
    ax.set_xlabel("Paired difference vs single call\n(verdict accuracy, fraction)")
    ax.text(-0.02, -0.85, "single call better", ha="right", va="center", color=fs.MUTED)
    ax.text(0.02, -0.85, "agent better", ha="left", va="center", color=fs.MUTED)
    fs.panel_label(fig, "b", 108.5, top - 6.5)


def panel_composition(fig, data, top: float) -> tuple[float, float]:
    left, width = 34.0, 44.0
    pairs = [(arm, name, tag) for arm in ARMS for name, tag in (("live", "v1"), ("live_v2", "v2"))]
    step, gap = 3.6, 1.6
    ypos, y = [], 0.0
    for i, _ in enumerate(pairs):
        ypos.append(y)
        y += step + (gap if i % 2 == 1 else 0)
    height = ypos[-1] + step
    ax = fs.axes_mm(fig, left, top, width, height)
    for (arm, name, tag), yp in zip(pairs, ypos, strict=True):
        rs = data[name][arm]
        n = len(rs)
        start = 0.0
        yc = yp + step / 2
        for key, _, _ in CLASSES:
            c = sum(classify(r) == key for r in rs)
            if c:
                ax.barh(
                    yc,
                    c / n,
                    left=start,
                    height=step * 0.62,
                    color=fs.OUTCOME[key],
                    edgecolor="white",
                    linewidth=0.4,
                )
            start += c / n
        malformed = sum(r["malformed_actions"] for r in rs)
        shown = "n/a" if arm == "lexical" else str(malformed)
        ax.text(1.03, yc, shown, va="center", ha="left", transform=ax.get_yaxis_transform())
        ax.text(-0.015, yc, tag, va="center", ha="right", transform=ax.get_yaxis_transform())
    for k in range(len(ARMS)):
        yc = (ypos[2 * k] + ypos[2 * k + 1] + step) / 2
        ax.text(
            -0.11,
            yc,
            ARM_NAME[ARMS[k]].replace(" (no model)", "\n(no model)"),
            va="center",
            ha="right",
            transform=ax.get_yaxis_transform(),
        )
    ax.text(
        1.03, -0.4, "Malformed\nsteps", va="bottom", ha="left", transform=ax.get_yaxis_transform()
    )
    ax.set_ylim(height, 0)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_locator(MultipleLocator(0.25))
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "0.25", "0.5", "0.75", "1"])
    ax.set_xlabel("Episodes (fraction), n = 20 per bar")
    fs.panel_label(fig, "c", 1.5, top - 5.5)
    return left, top + height


def panel_tiles(fig, data, top: float) -> None:
    cols = []
    for name, label, _ in CONDITIONS[1:]:
        arms = data[name]
        model = label.split(", ")[1]
        for arm in ARMS:
            for run in sorted({r["run"] for r in arms.get(arm, [])}):
                rs = {r["task_id"]: r for r in arms[arm] if r["run"] == run}
                cols.append((f"{ARM_NAME[arm]}, run {run + 1}", model, rs))
    qs = sorted({q for *_, rs in cols for q in rs})
    # difficulty: mean over the 7 arm-model pairs of each pair's run-averaged accuracy
    pairs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for lab, model, rs in cols:
        pairs[(lab.rsplit(", run", 1)[0], model)].append(rs)
    correct = {
        q: float(np.mean([np.mean([rs[q]["verdict_correct"] for rs in v]) for v in pairs.values()]))
        for q in qs
    }
    qs.sort(key=lambda q: (-correct[q], q))
    tile_w, tile_h, head = 4.3, 3.1, 3.6
    left = 132.0
    marg_h = 7.0
    n_mini = sum(1 for c in cols if c[1] == "gpt-4.1-mini")
    grid_h = len(cols) * tile_h + 2 * head
    width = len(qs) * tile_w
    ax = fs.axes_mm(fig, left, top + marg_h + 0.8, width, grid_h)
    fs.bare(ax)
    ys = []
    for i, (_, _, rs) in enumerate(cols):
        y0 = i * tile_h + (2 * head if i >= n_mini else head)
        ys.append(y0 + tile_h / 2)
        for j, q in enumerate(qs):
            key = classify(rs[q])
            ax.add_patch(
                fs.plt.Rectangle(
                    (j * tile_w, y0),
                    tile_w,
                    tile_h,
                    facecolor=fs.OUTCOME[key],
                    edgecolor="white",
                    linewidth=0.6,
                )
            )
            code = next(c for k, _, c in CLASSES if k == key)
            ax.text(
                j * tile_w + tile_w / 2,
                y0 + tile_h / 2 + 0.05,
                code,
                ha="center",
                va="center",
                color=fs.OUTCOME_TEXT[key],
            )
    for txt, y in (
        ("gpt-4.1-mini, 2 runs per arm", head * 0.55),
        ("claude-sonnet-4.6, 1 run per arm", n_mini * tile_h + head * 1.55),
    ):
        ax.text(0, y, txt, ha="left", va="center", color=fs.MUTED)
    ax.set_xlim(0, width)
    ax.set_ylim(grid_h, 0)
    ax.set_yticks(ys, [c[0] for c in cols])
    ax.set_xticks([(j + 0.5) * tile_w for j in range(len(qs))], [q.replace("h2-q", "") for q in qs])
    ax.set_xlabel("Held-out v2 question, easiest to hardest")
    # marginal bar: fraction of the 11 cells in each column with a right verdict
    mx = fs.axes_mm(fig, left, top, width, marg_h)
    mx.bar(
        [(j + 0.5) * tile_w for j in range(len(qs))],
        [correct[q] for q in qs],
        width=tile_w * 0.7,
        color=fs.MUTED,
        linewidth=0,
    )
    mx.set_xlim(0, width)
    mx.set_ylim(0, 1)
    mx.set_yticks([0, 1], ["0", "1"])
    mx.set_xticks([])
    mx.spines["bottom"].set_visible(False)
    mx.set_ylabel(
        "Right verdict\n(mean of 7 arms)", rotation=0, ha="right", va="center", labelpad=4
    )
    fs.panel_label(fig, "d", 103.5, top - 2.5)


def figure1(data, out: Path) -> list[Path]:
    fig = fs.figure(fs.FULL_WIDTH, 128)
    panel_accuracy(fig, data, top=9.0)
    panel_forest(fig, data, top=9.0)
    left, bottom = panel_composition(fig, data, top=69.0)
    panel_tiles(fig, data, top=66.0)
    key = fig.add_axes((0, 0, 1, 1), facecolor="none")
    key.set_axis_off()
    handles = fs.outcome_handles([(k, f"{c}  {lab}") for k, lab, c in CLASSES])
    fw, fh = fig.get_size_inches() / fs.MM
    key.legend(
        handles=handles,
        loc="upper left",
        ncol=2,
        handlelength=1.0,
        bbox_to_anchor=(4.0 / fw, 1 - (bottom + 10.0) / fh),
        columnspacing=1.0,
    )
    return fs.save(fig, out, "fig1_main")


# Supplementary figures ------------------------------------------------------


def figure_s1(data, out: Path) -> list[Path]:
    fig = fs.figure(fs.FULL_WIDTH, 56)
    panels = [
        ("v1\ngpt-4.1-mini", [("live", "agent", False), ("live", "agent_no_expand", False)]),
        ("v2\ngpt-4.1-mini", [("live_v2", "agent", False), ("live_v2", "agent_no_expand", False)]),
        ("v2\nclaude-sonnet-4.6", [("live_v2_sonnet", "agent", True)]),
    ]
    dodge = {"agent": -0.06, "agent_no_expand": 0.06}
    all_handles: dict = {}
    for j, (title, series) in enumerate(panels):
        ax = fs.axes_mm(fig, 16 + j * 58, 8, 44, 32)
        for name, arm, second in series:
            vals = [r["tool_calls"] for r in data[name][arm]]
            shift = dodge[arm] if len(series) > 1 else 0.0
            x, y = fs.ecdf(vals)
            t = ARM_TYPE[arm]
            ax.step(x + shift, y, where="post", **fs.line_kw(t, second, width=1.1))
            ux = np.unique(vals)
            uy = np.array([np.mean(np.asarray(vals) <= u) for u in ux])
            ax.plot(ux + shift, uy, **{**fs.marker_kw(t, second, size=3.0), "clip_on": False})
            med = float(np.median(vals))
            STATS[f"tool_calls/{name}/{arm}"] = {"n": len(vals), "median": med}
            model = "claude-sonnet-4.6" if second else "gpt-4.1-mini"
            all_handles[(arm, second)] = fs.arm_handles(
                [(f"{ARM_NAME[arm]}, {model}", t, second)], line=True
            )[0]
        ax.axvline(10, color=fs.MUTED, linewidth=0.6, linestyle=(0, (1, 1.5)), zorder=5)
        ax.text(9.9, 0.02, "cap", ha="right", va="bottom", color=fs.MUTED)
        ax.set_xlim(0, 10.6)
        ax.set_ylim(0, 1.03)
        ax.spines["left"].set_bounds(0, 1)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
        fs.tidy_ticks(ax)
        ax.set_xlabel("Tool calls per episode")
        if j == 0:
            ax.set_ylabel("Cumulative fraction\nof episodes")
        else:
            ax.set_yticklabels([])
        ax.set_title(title)
        fs.panel_label(fig, "abc"[j], 1.5 if j == 0 else 9.0 + j * 58, 2.0)
    key = fs.axes_mm(fig, 16, 51, 160, 3)
    key.set_axis_off()
    key.legend(handles=list(all_handles.values()), loc="center", ncol=3, columnspacing=2.0)
    return fs.save(fig, out, "figS1_tool_calls")


def figure_s2(data, out: Path) -> list[Path]:
    fig = fs.figure(fs.FULL_WIDTH, 64)
    for j, (name, label, second) in enumerate(CONDITIONS):
        ax = fs.axes_mm(fig, 16 + j * 58, 10, 44, 40)
        arms = [a for a in ARMS if a in data[name]]
        handles = []
        for arm in arms:
            rs = data[name][arm]
            x, xlo, xhi, _, n = rate(rs, "verdict_correct")
            k_c = sum(r["citations_valid"] for r in rs)
            n_c = sum(r["citations_emitted"] for r in rs)
            y, ylo, yhi = fs.wilson(k_c, n_c)
            STATS[f"citation_validity/{name}/{arm}"] = {
                "k": k_c,
                "n": n_c,
                "rate": y,
                "wilson95": [ylo, yhi],
            }
            # in (c) every arm has validity 1; offset only the accuracy intervals
            shift = {"lexical": 0.0, "single_call": -0.025, "agent": -0.05}[arm] if second else 0
            t = ARM_TYPE[arm]
            ax.plot([xlo, xhi], [y + shift] * 2, **fs.line_kw(t, second, width=0.8))
            ax.plot([x, x], [ylo, yhi], **fs.line_kw(t, second, width=0.8))
            ax.plot([x], [y], **{**fs.marker_kw(t, second), "clip_on": False})
            handles += fs.arm_handles([(ARM_NAME[arm], t, second)])
        ax.legend(handles=handles, loc="lower left")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.06)
        ax.spines["bottom"].set_bounds(0, 1)
        ax.spines["left"].set_bounds(0, 1)
        ticks = [0, 0.25, 0.5, 0.75, 1]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        fs.tidy_ticks(ax)
        ax.set_xlabel("Verdict accuracy (fraction)")
        if j == 0:
            ax.set_ylabel("Citation validity (fraction)")
        ax.set_title(label.replace(", ", "\n"))
        fs.panel_label(fig, "abc"[j], 1.5 if j == 0 else 9.0 + j * 58, 2.0)
    return fs.save(fig, out, "figS2_citation_vs_accuracy")


def main(argv: list[str] | None = None) -> list[Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "figures")
    args = parser.parse_args(argv)
    fs.apply()
    data = {name: by_arm(load(name)) for name, _, _ in CONDITIONS}
    paths = figure1(data, args.out)
    paths += figure_s1(data, args.out)
    paths += figure_s2(data, args.out)
    stats = args.out / "figure_stats.json"
    rounded = {
        k: {
            f: (
                round(v, 4)
                if isinstance(v, float)
                else [round(x, 4) for x in v] if isinstance(v, list) else v
            )
            for f, v in d.items()
        }
        for k, d in sorted(STATS.items())
    }
    meta = {
        "interval": "Wilson 95% for rates; paired percentile bootstrap 95% for differences",
        "bootstrap_resamples": fs.N_BOOT,
        "seed": fs.SEED,
        "resampling_unit": "task",
    }
    stats.write_text(
        json.dumps({"method": meta, "values": rounded}, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return paths + [stats]


if __name__ == "__main__":
    for p in main():
        print(f"wrote {p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p}")
