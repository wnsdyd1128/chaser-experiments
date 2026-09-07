#!/usr/bin/env python3
"""Plot the measured L1 miss ratio of the two exp4 access patterns.

The reuse-distance figure states what an LRU model reads off the histogram.
This one states what a cache actually did with the same two patterns: the host
mirror of the RTEMS loop, run under cachegrind with the GR740 geometry forced
on the command line. The model's reading is drawn over each bar, so the figure
also says how far the model is from the measurement.

The figure carries data only. Its explanation belongs in the paper caption,
which exp4-ca-mean-rd/README.md keeps next to the numbers.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import plot_ca_mean_rd as mean_rd_module
from plot_style import sci

A_COLOR = "#3A6EA5"
B_COLOR = "#2E8B62"
MODEL_COLOR = "#1F1F1F"
L1_LINES = mean_rd_module.GR740_L1_LINES


def model_miss_pct(case: dict) -> float:
    """Share of reuses an LRU cache of L1's size misses, from the histogram."""
    hist = mean_rd_module.histogram(case)
    total = sum(hist.values())
    return 100.0 * sum(count for rd, count in hist.items()
                       if rd >= L1_LINES) / total


def label_of(case: dict) -> str:
    """Workload letter, what its reuses do, and the footprint it touches."""
    letter = "A" if case["repeats"] == 1 else "B"
    if case["repeats"] == 1:
        shape = f"every reuse at $\\delta$ = {case['distinct'] - 1}"
    else:
        share = 100.0 * (case["repeats"] - 1) / case["repeats"]
        shape = f"{share:.0f}% of reuses at $\\delta$ = 0"
    return (f"$\\mathbf{{{letter}}}$\n{shape}\n"
            f"{case['working_set_bytes'] // 1024} KiB")


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    root = Path(__file__).resolve().parents[1]
    cases = []
    with (root / "results/exp4_cachegrind.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            cases.append({
                "case": row["case"],
                "distinct": int(row["distinct"]),
                "repeats": int(row["repeats"]),
                "cycles": int(row["cycles"]),
                "working_set_bytes": int(row["working_set_bytes"]),
                "measured": float(row["d1_rd_miss_pct"]),
            })
    cases.sort(key=lambda case: case["repeats"])

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 11,
        "axes.linewidth": 1.0,
    })

    x = list(range(len(cases)))
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    ax.bar(x, [case["measured"] for case in cases], 0.46,
           color=[A_COLOR, B_COLOR][:len(cases)], edgecolor="0.05",
           linewidth=0.9)

    top = 118.0
    ax.set_ylim(0, top)
    for idx, case in enumerate(cases):
        ax.text(idx, case["measured"] + 2.0, f"{case['measured']:.1f}%",
                ha="center", va="bottom", fontsize=11)
        model = model_miss_pct(case)
        ax.plot([idx - 0.30, idx + 0.30], [model, model], color=MODEL_COLOR,
                linewidth=2.0, solid_capstyle="butt")
        ax.text(idx + 0.34, model, f"model {model:.1f}%", ha="left",
                va="center", fontsize=9.5, color=MODEL_COLOR)

    mean = float(mean_rd_module.mean_rd(cases[0]))
    ax.text(0.02, 0.965,
            f"both workloads: mean $\\delta$ = {mean:.0f}"
            f" $\\cdot$ CA = {sci(1 / (1 + mean))}",
            transform=ax.transAxes, ha="left", va="top", fontsize=10,
            color="0.25")

    ax.set_ylabel("L1 read miss ratio (%)")
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks(x)
    ax.set_xticklabels([label_of(case) for case in cases], fontsize=10.5)
    ax.set_xlim(-0.6, len(cases) - 0.25 + 0.75)

    handles = [
        Patch(facecolor=A_COLOR, edgecolor="0.05", label="A, measured"),
        Patch(facecolor=B_COLOR, edgecolor="0.05", label="B, measured"),
        Line2D([], [], color=MODEL_COLOR, linewidth=2.0,
               label="LRU model of the histogram"),
    ]
    ax.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
              bbox_to_anchor=(0.5, 1.13), handlelength=1.6, fontsize=9.5)

    fig.tight_layout(pad=0.6)
    out = root / "results/exp4_measured_miss.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(root / "results/exp4_measured_miss.pdf", bbox_inches="tight")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
