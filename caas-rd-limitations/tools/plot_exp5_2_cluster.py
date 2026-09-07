#!/usr/bin/env python3
"""Plot exp5-2: the same CAAS input, one case needing a cluster and one not.

Mean victim response time under each placement. The two cases carry the same CA
and the same U and differ only in stride, so the CAAS feature vector cannot
separate them, while the number of cache lines a victim holds decides whether
bounded migration inside a cluster is worth its queueing. The number the figure
is built around is what the model's answer costs against the measured best.

The figure carries data only. Its explanation belongs in the paper caption,
which exp5-2-ca-cluster-mismatch/README.md keeps next to the numbers.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from plot_style import BEST_MARKER, PREDICTION_MARKER, decision_handles, sci

COLORS = {
    "global": "#C44E52",
    "partitioned": "#4C72B0",
    "clustered": "#55A868",
    "partitioned_alt": "#BFBFBF",
}
LABELS = {
    "global": "GLOBAL",
    "partitioned": "PARTITIONED",
    "clustered": "CLUSTERED",
    "partitioned_alt": "PARTITIONED$_{alt}$",
}
ORDER = ("global", "partitioned", "clustered", "partitioned_alt")
PENALTY_COLOR = "#B02418"
BAR_WIDTH = 0.19
MARK_Y = 0.74
PENALTY_Y = 0.81


def kind_of(row: dict) -> str:
    """How the victim's addresses lie in memory, which is the figure's axis."""
    return "Packed" if int(row["victim_stride"]) < 32 else "Spread"


def footprint_of(row: dict) -> str:
    """Victim footprint in the unit that keeps it a small number."""
    size = int(row["victim_bytes"])
    return f"{size} B" if size < 1024 else f"{size // 1024} KiB"


def bar_x(index: int, series: str) -> float:
    """Centre of one bar of a group."""
    return index + (ORDER.index(series) - 1.5) * BAR_WIDTH


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    root = Path(__file__).resolve().parents[1]
    rows = list(csv.DictReader(
        (root / "results/exp5_2_cluster_mismatch.csv").open()))

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 11,
        "axes.linewidth": 1.0,
        "hatch.linewidth": 1.0,
    })

    x = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    heights: dict[str, list[float]] = {}
    for key in ORDER:
        heights[key] = [float(row[f"{key}_resp_mean_us"]) for row in rows]
        ax.bar([bar_x(i, key) for i in x], heights[key], BAR_WIDTH,
               color=COLORS[key], edgecolor="0.05", linewidth=0.9,
               hatch="//" if key == "partitioned_alt" else None)

    top = max(max(values) for values in heights.values()) * 1.62
    ax.set_ylim(0, top)

    for idx, row in enumerate(rows):
        best = row["measured_best"].lower()
        predicted = row["rf_prediction"].lower()
        for key in dict.fromkeys((predicted, best)):
            ax.text(bar_x(idx, key), heights[key][idx] + top * 0.012,
                    f"{heights[key][idx]:.1f}", ha="center", va="bottom",
                    fontsize=8.5)

        ax.plot([bar_x(idx, predicted)], [MARK_Y * top], **PREDICTION_MARKER)
        ax.plot([bar_x(idx, best)], [MARK_Y * top], **BEST_MARKER)
        ax.text(idx, PENALTY_Y * top, f"+{float(row['rf_gap_pct']):.1f}%",
                ha="center", va="bottom", fontsize=12, fontweight="bold",
                color=PENALTY_COLOR if row["verdict"] == "wrong" else "0.4")

    if len(rows) == 2 and rows[0]["ca_victim"] == rows[1]["ca_victim"]:
        tasks = int(rows[0]["victims"]) + int(rows[0]["polluters"]) \
            if "victims" in rows[0] else 8
        bracket = top * 0.93
        ax.plot([0, 0, 1, 1],
                [bracket - top * 0.02, bracket, bracket, bracket - top * 0.02],
                color="0.25", linewidth=1.0)
        ax.text(0.5, bracket + top * 0.008,
                f"{tasks} tasks $\\cdot$ CA = {sci(float(rows[0]['ca_victim']))}",
                ha="center", va="bottom", fontsize=9.5, color="0.25")

    ax.set_ylabel("Mean victim response time (\u00b5s)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"$\\mathbf{{{kind_of(row)}}}$\n{footprint_of(row)}"
                        for row in rows], fontsize=11)

    best_handle, prediction_handle = decision_handles()
    handles = [
        Patch(facecolor=COLORS["global"], edgecolor="0.05", label="GLOBAL"),
        Patch(facecolor=COLORS["partitioned"], edgecolor="0.05",
              label="PARTITIONED"),
        Patch(facecolor=COLORS["clustered"], edgecolor="0.05",
              label="CLUSTERED"),
        Patch(facecolor=COLORS["partitioned_alt"], edgecolor="0.05",
              hatch="////", label=LABELS["partitioned_alt"]),
        best_handle,
        prediction_handle,
    ]
    ax.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
              bbox_to_anchor=(0.5, 1.19), handlelength=1.5, handleheight=0.9,
              columnspacing=1.4, fontsize=9.5, markerscale=1.0)

    fig.tight_layout(pad=0.6)
    out = root / "results/exp5_2_cluster_bar.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(root / "results/exp5_2_cluster_bar.pdf", bbox_inches="tight")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
