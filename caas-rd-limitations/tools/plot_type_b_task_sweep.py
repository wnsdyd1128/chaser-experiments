#!/usr/bin/env python3
"""Plot TYPE-B task-count sweep as a grouped bar chart."""

from __future__ import annotations

import csv
import os
from pathlib import Path


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    root = Path(__file__).resolve().parents[1]
    rows = list(csv.DictReader((root / "results/type_b_gp_task_sweep_summary.csv").open()))
    tasks = [int(row["tasks"]) for row in rows]
    global_mean_ms = [float(row["global_mean_avg_ms"]) for row in rows]
    partitioned_mean_ms = [float(row["partitioned_mean_avg_ms"]) for row in rows]
    global_ms = [float(row["global_worst_avg_ms"]) for row in rows]
    partitioned_ms = [float(row["partitioned_worst_avg_ms"]) for row in rows]

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 11,
        "axes.linewidth": 1.0,
        "hatch.linewidth": 1.0,
    })

    global_mean_color = "#E07B7F"
    global_worst_color = "#C44E52"
    partitioned_mean_color = "#7DA0D4"
    partitioned_worst_color = "#4C72B0"
    width = 0.18
    x = list(range(len(tasks)))

    fig, ax = plt.subplots(figsize=(9.4, 4.1))
    bars = [
        ax.bar([i - 1.5 * width for i in x], global_mean_ms, width,
               color=global_mean_color, edgecolor="0.05", linewidth=0.9,
               label="RF prediction (GLOBAL), mean"),
        ax.bar([i - 0.5 * width for i in x], partitioned_mean_ms, width,
               color=partitioned_mean_color, edgecolor="0.05", linewidth=0.9,
               label="PARTITIONED, mean"),
        ax.bar([i + 0.5 * width for i in x], global_ms, width,
               color=global_worst_color, edgecolor="0.05", linewidth=0.9,
               hatch="//", label="RF prediction (GLOBAL), worst"),
        ax.bar([i + 1.5 * width for i in x], partitioned_ms, width,
               color=partitioned_worst_color, edgecolor="0.05", linewidth=0.9,
               hatch="//", label="PARTITIONED, worst"),
    ]

    for group in bars:
        for bar in group:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height + 5,
                    f"{height:.1f}", ha="center", va="bottom", fontsize=8,
                    rotation=90)

    ax.set_ylabel("Job execution time (ms)")
    ax.set_xlabel("Number of tasks")
    ax.set_xticks(x)
    ax.set_xticklabels([str(item) for item in tasks], rotation=30, ha="right")
    ax.set_ylim(0, max(global_ms) * 1.52)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.0)
    ax.text(0.015, 0.965, "Lower is better ↓", transform=ax.transAxes,
            ha="left", va="top", fontsize=9)

    handles = [
        Patch(facecolor=global_worst_color, edgecolor="0.05",
              label="RF prediction (GLOBAL)"),
        Patch(facecolor=partitioned_worst_color, edgecolor="0.05",
              label="PARTITIONED"),
        Patch(facecolor="white", edgecolor="0.05", label="Mean"),
        Patch(facecolor="white", edgecolor="0.05", hatch="////", label="Worst"),
    ]
    ax.legend(handles=handles, loc="upper right", ncol=4, frameon=False,
              handlelength=1.5, handleheight=0.9, columnspacing=0.8,
              borderaxespad=0.35, fontsize=8.5)

    fig.tight_layout(pad=0.7)
    out = root / "results/type_b_gp_task_sweep_bar.png"
    fig.savefig(out, dpi=220)
    fig.savefig(root / "results/type_b_gp_task_sweep_bar.pdf")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
