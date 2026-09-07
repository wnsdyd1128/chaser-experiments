#!/usr/bin/env python3
"""Plot the exp5-1 cases that share a CA: one CAAS input, two answers.

Only pairs are drawn, one per task-set size: the two cases under a bracket touch
the same number of distinct addresses, so CA is identical and the measured
standalone utilization agrees within a couple of percent. They differ in stride
alone, which decides how many cache lines those addresses occupy.

The figure carries data only. Its explanation belongs in the paper caption,
which exp5-1-ca-arch-mismatch/README.md keeps next to the numbers.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from plot_style import BEST_MARKER, PREDICTION_MARKER, decision_handles, sci

GLOBAL_MEAN_COLOR = "#E07B7F"
GLOBAL_WORST_COLOR = "#C44E52"
PART_MEAN_COLOR = "#7DA0D4"
PART_WORST_COLOR = "#4C72B0"
PENALTY_COLOR = "#B02418"
BAR_WIDTH = 0.19
MARK_Y = 0.68
PENALTY_Y = 0.755
OFFSETS = {"global_mean": -1.5, "partitioned_mean": -0.5,
           "global_worst": 0.5, "partitioned_worst": 1.5}


def cost(pair: list[dict]) -> float:
    """What the model's answer costs on the worse-served member of a pair."""
    return max(float(row["rf_gap_pct"]) for row in pair)


def pairs(rows: list[dict]) -> list[dict]:
    """The costliest pair at each task-set size, packed member first.

    A pair is two cases sharing CA, U and task counts, so CAAS reads them as one
    input. Taking the costliest pair per task count keeps the figure on the
    cases the model gets wrong while showing that the failure is not a single
    task-set size; the packed twin comes along because it is the reason the
    model cannot tell the two apart.
    """
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["ca_victim"], row["victims"]), []).append(row)

    complete = [sorted(group, key=lambda row: int(row["victim_stride"]))
                for group in grouped.values() if len(group) == 2]

    worst_per_size: dict[int, list[dict]] = {}
    for pair in complete:
        tasks = int(pair[0]["victims"]) + int(pair[0]["polluters"])
        if tasks not in worst_per_size or cost(pair) > cost(worst_per_size[tasks]):
            worst_per_size[tasks] = pair
    return [row for tasks in sorted(worst_per_size)
            for row in worst_per_size[tasks]]


def kind_of(row: dict) -> str:
    """How the victim's addresses lie in memory, which is the figure's axis."""
    return "Packed" if int(row["victim_stride"]) < 32 else "Spread"


def footprint_of(row: dict) -> str:
    """Victim footprint in the unit that keeps it a small number."""
    size = int(row["victim_bytes"])
    return f"{size} B" if size < 1024 else f"{size // 1024} KiB"


def bar_x(index: int, series: str) -> float:
    """Centre of one bar of a group."""
    return index + OFFSETS[series] * BAR_WIDTH


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    root = Path(__file__).resolve().parents[1]
    rows = pairs(list(csv.DictReader(
        (root / "results/exp5_1_arch_mismatch.csv").open())))

    heights = {
        "global_mean": [float(row["global_victim_mean_us"]) for row in rows],
        "partitioned_mean": [float(row["partitioned_victim_mean_us"])
                             for row in rows],
        "global_worst": [float(row["global_victim_worst_us"]) for row in rows],
        "partitioned_worst": [float(row["partitioned_victim_worst_us"])
                              for row in rows],
    }

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 11,
        "axes.linewidth": 1.0,
        "hatch.linewidth": 1.0,
    })

    x = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    styles = {
        "global_mean": (GLOBAL_MEAN_COLOR, None),
        "partitioned_mean": (PART_MEAN_COLOR, None),
        "global_worst": (GLOBAL_WORST_COLOR, "//"),
        "partitioned_worst": (PART_WORST_COLOR, "//"),
    }
    for series, (color, hatch) in styles.items():
        ax.bar([bar_x(i, series) for i in x], heights[series], BAR_WIDTH,
               color=color, edgecolor="0.05", linewidth=0.9, hatch=hatch)

    top = max(heights["global_worst"] + heights["partitioned_worst"]) * 1.66
    ax.set_ylim(0, top)

    for idx, row in enumerate(rows):
        best = f"{row['measured_best'].lower()}_mean"
        predicted = f"{row['rf_prediction'].lower()}_mean"

        # Values only on the two bars the decisions point at.
        for series in dict.fromkeys((predicted, best)):
            ax.text(bar_x(idx, series), heights[series][idx] + top * 0.012,
                    f"{heights[series][idx]:.1f}", ha="center", va="bottom",
                    fontsize=8.5)

        # Both marks sit on one line above every bar, so their height carries
        # no meaning and only the bar they stand over does: two marks apart is
        # a misprediction, the dot inside the ring is agreement.
        ax.plot([bar_x(idx, predicted)], [MARK_Y * top], **PREDICTION_MARKER)
        ax.plot([bar_x(idx, best)], [MARK_Y * top], **BEST_MARKER)

        if row["verdict"] == "wrong":
            ax.text(idx, PENALTY_Y * top, f"+{float(row['rf_gap_pct']):.1f}%",
                    ha="center", va="bottom", fontsize=12, fontweight="bold",
                    color=PENALTY_COLOR)

    bracket = top * 0.86
    for left in range(0, len(rows) - 1, 2):
        row = rows[left]
        tasks = int(row["victims"]) + int(row["polluters"])
        ax.plot([left, left, left + 1, left + 1],
                [bracket - top * 0.02, bracket, bracket, bracket - top * 0.02],
                color="0.25", linewidth=1.0)
        ax.text(left + 0.5, bracket + top * 0.008,
                f"{tasks} tasks $\\cdot$ CA = {sci(float(row['ca_victim']))}",
                ha="center", va="bottom", fontsize=9.5, color="0.25")

    ax.set_ylabel("Victim job execution time (\u00b5s)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"$\\mathbf{{{kind_of(row)}}}$\n{footprint_of(row)}"
                        for row in rows], fontsize=11)

    best_handle, prediction_handle = decision_handles()
    # Column-major order: architecture, bar style, decision mark.
    handles = [
        Patch(facecolor=GLOBAL_WORST_COLOR, edgecolor="0.05", label="GLOBAL"),
        Patch(facecolor=PART_WORST_COLOR, edgecolor="0.05",
              label="PARTITIONED"),
        Patch(facecolor="white", edgecolor="0.05", label="Solid: mean"),
        Patch(facecolor="white", edgecolor="0.05", hatch="////",
              label="Hatched: worst-case"),
        best_handle,
        prediction_handle,
    ]
    ax.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
              bbox_to_anchor=(0.5, 1.19), handlelength=1.5, handleheight=0.9,
              columnspacing=1.6, fontsize=9.5, markerscale=1.0)

    fig.tight_layout(pad=0.6)
    out = root / "results/exp5_1_collision_bar.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(root / "results/exp5_1_collision_bar.pdf", bbox_inches="tight")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
