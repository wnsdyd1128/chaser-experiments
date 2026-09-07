#!/usr/bin/env python3
"""Plot the exp5-1 capacity step: CA slides, the architecture decision jumps.

Only the full-stride cases are drawn, so the victim footprint grows with the
address count and CA falls smoothly along with it. What the measurement does is
not smooth: PARTITIONED pins two victims per core, so its gain survives only
while the pair still fits the 512-line L1, and the sign flips there.

The figure carries data only. Its explanation belongs in the paper caption,
which exp5-1-ca-arch-mismatch/README.md keeps next to the numbers.
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

from plot_style import sci

L1_LINES = 512
GLOBAL_COLOR = "#C44E52"
PARTITIONED_COLOR = "#4C72B0"
TIE_COLOR = "#9A9A9A"
CA_COLOR = "#1F1F1F"



def band_limits(values: list[float], low: float, high: float) -> tuple[float, float]:
    """Log-axis limits that place `values` between two axes fractions.

    The CA curve and the bars share one panel, so the curve is given its own
    band above the bars instead of crossing them.
    """
    log_min, log_max = math.log10(min(values)), math.log10(max(values))
    span = (log_max - log_min) / (high - low)
    bottom = log_min - low * span
    return 10.0 ** bottom, 10.0 ** (bottom + span)


def tick_label(row: dict) -> str:
    """Case name and victim footprint; the rest is caption material."""
    return f"{row['case']}\n{int(row['victim_bytes']) // 1024} KiB"


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    root = Path(__file__).resolve().parents[1]
    rows = [row for row in csv.DictReader(
        (root / "results/exp5_1_arch_mismatch.csv").open())
        if int(row["victim_stride"]) == 32 and int(row["victims"]) == 4]
    rows.sort(key=lambda row: int(row["victim_bytes"]))

    gain = [-float(row["delta_victim_mean_pct"]) for row in rows]
    ca = [float(row["ca_victim"]) for row in rows]

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 11,
        "axes.linewidth": 1.0,
    })

    x = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    colors = {"PARTITIONED": PARTITIONED_COLOR, "GLOBAL": GLOBAL_COLOR,
              "TIE": TIE_COLOR}
    bars = ax.bar(x, gain, 0.5,
                  color=[colors[row["measured_best"]] for row in rows],
                  edgecolor="0.05", linewidth=0.9)
    for bar, value in zip(bars, gain):
        inside = abs(value) > 6
        ax.text(bar.get_x() + bar.get_width() / 2,
                value / 2 if inside else value + (1.1 if value > 0 else -1.1),
                f"{value:+.1f}%", ha="center", va="center" if inside else
                ("bottom" if value > 0 else "top"), fontsize=10,
                color="white" if inside else "0.15")

    ax.axhline(0, color="0.2", linewidth=1.0)
    ax.set_ylim(min(gain) * 1.8, max(gain) * 2.4)
    ax.set_ylabel("Measured gain of PARTITIONED\nover GLOBAL (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([tick_label(row) for row in rows], fontsize=10)

    boundary = next(idx for idx, row in enumerate(rows)
                    if 2 * int(row["victim_lines"]) >= L1_LINES)
    ax.axvline(boundary - 0.5, color="0.35", linewidth=1.1,
               linestyle=(0, (5, 3)))
    ax.text(boundary - 0.42, min(gain) * 1.55, "Victim pair exceeds L1",
            fontsize=10, color="0.25", ha="left", va="center")

    ax2 = ax.twinx()
    ax2.plot(x, ca, color=CA_COLOR, marker="o", markersize=5, linewidth=1.4)
    for idx, value in enumerate(ca):
        ax2.annotate(sci(value), (idx, value), textcoords="offset points",
                     xytext=(0, 9), ha="center", fontsize=9, color=CA_COLOR)
    ax2.set_yscale("log")
    ax2.set_ylim(*band_limits(ca, 0.70, 0.93))
    ax2.set_yticks([10.0 ** exponent for exponent in (-3, -2)])
    ax2.minorticks_off()
    ax2.set_ylabel("CA of the victim task")

    handles = [
        Patch(facecolor=PARTITIONED_COLOR, edgecolor="0.05",
              label="PARTITIONED"),
        Patch(facecolor=GLOBAL_COLOR, edgecolor="0.05", label="GLOBAL"),
        Patch(facecolor=TIE_COLOR, edgecolor="0.05", label="Tie (<5%)"),
        Line2D([], [], color=CA_COLOR, marker="o", markersize=5, label="CA"),
    ]
    ax.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
              bbox_to_anchor=(0.5, 1.13), fontsize=10)

    fig.tight_layout(pad=0.6)
    out = root / "results/exp5_1_capacity_step.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(root / "results/exp5_1_capacity_step.pdf", bbox_inches="tight")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
