#!/usr/bin/env python3
"""Plot the CA saturation limitation: linear-in-RD CA vs step-shaped cache cost.

Input is the cachegrind sweep CSV produced by tools/run_cachegrind_sweep.sh.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

GR740_L1_BYTES = 16 * 1024
GR740_L2_BYTES = 2 * 1024 * 1024

CA_COLOR = "#C44E52"
D1_COLOR = "#4C72B0"
LL_COLOR = "#55A868"


def ca_closed_form(distinct: int, sweeps: int) -> float:
    """CA of a cyclic sweep over `distinct` addresses repeated `sweeps` times.

    Each iteration issues a load and a store to the same address, so the reuse
    histogram holds only RD = 0 (the store) and RD = distinct - 1 (the next
    sweep). Substituting those into CA = sum(r) / sum((delta + 1) * r) leaves
    the expression below, which tends to 2 / (distinct + 2) as sweeps grows.
    Reproduces YARDA's element-granularity output exactly.
    """
    reuses = 2 * sweeps - 1
    weighted = (distinct - 1) * (sweeps - 1)
    return reuses / (reuses + weighted)


def load_points(path: Path) -> list[dict]:
    """Read the measured sweep CSV and derive CA for each case."""
    points = []
    for row in csv.DictReader(path.open(encoding="utf-8")):
        distinct, sweeps = int(row["distinct"]), int(row["sweeps"])
        points.append({
            "distinct": distinct,
            "working_set": int(row["working_set_bytes"]),
            "sweeps": sweeps,
            "d1": float(row["d1_rd_miss_pct"]),
            "ll": float(row["ll_rd_miss_pct"]),
            "ca": ca_closed_form(distinct, sweeps),
        })
    return sorted(points, key=lambda item: item["distinct"])


def tier(working_set: int) -> str:
    if working_set <= GR740_L1_BYTES:
        return "L1"
    if working_set <= GR740_L2_BYTES:
        return "L2"
    return "RAM"


def human_bytes(value: int) -> str:
    for unit, scale in (("MB", 1 << 20), ("KB", 1 << 10)):
        if value >= scale:
            size = value / scale
            return f"{size:.0f} {unit}" if size == int(size) else f"{size:.1f} {unit}"
    return f"{value} B"


def draw_panel_a(ax, points):
    d = [p["distinct"] for p in points]
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")

    l1_d = GR740_L1_BYTES // 32
    l2_d = GR740_L2_BYTES // 32
    ax.axvspan(min(d) * 0.7, l1_d, color="0.93", zorder=0)
    ax.axvspan(l2_d, max(d) * 1.4, color="0.86", zorder=0)
    ax.set_xlim(min(d) * 0.7, max(d) * 1.4)

    ca_line, = ax.plot(d, [p["ca"] for p in points], marker="o", ms=5.5, lw=1.7,
                       color=CA_COLOR, zorder=3,
                       label="CA (address-based)")
    ax.set_xlabel("D = distinct addresses touched per sweep   "
                  "(reuse distance $\\delta$ = D - 1)")
    ax.set_ylabel("CA", color=CA_COLOR)
    ax.tick_params(axis="y", colors=CA_COLOR)

    twin = ax.twinx()
    d1_line, = twin.plot(d, [p["d1"] for p in points], marker="s", ms=5.5, lw=1.7,
                         ls="--", color=D1_COLOR, zorder=3,
                         label="L1 miss rate (cachegrind)")
    ll_line, = twin.plot(d, [p["ll"] for p in points], marker="^", ms=5.5, lw=1.7,
                         ls="-.", color=LL_COLOR, zorder=3,
                         label="L2 miss rate (cachegrind)")
    twin.set_ylabel("Read miss rate (%)")
    twin.set_ylim(-5, 118)

    for boundary, label in ((l1_d, f"L1 {human_bytes(GR740_L1_BYTES)}"),
                            (l2_d, f"L2 {human_bytes(GR740_L2_BYTES)}")):
        ax.axvline(boundary, color="0.3", ls=":", lw=1.3, zorder=1)
        twin.text(boundary, 112, f" {label}", fontsize=8, color="0.15",
                  ha="left", va="top", rotation=90)

    handles = [ca_line, d1_line, ll_line]
    twin.legend(handles, [h.get_label() for h in handles], loc="lower left",
                frameon=False, fontsize=8.5, bbox_to_anchor=(0.02, 0.05))
    ax.set_title("(a) CA keeps falling; the cache cost saturates",
                 fontsize=10, pad=6)


def draw_panel_b(ax, pairs):
    from matplotlib.patches import Patch

    width = 0.3
    x = list(range(len(pairs)))
    ax.set_yscale("log")
    ax.axhline(1.0, color="0.3", ls=":", lw=1.3)

    groups = [
        ax.bar([i - width / 2 for i in x], [p["ca_ratio"] for p in pairs], width,
               color=CA_COLOR, edgecolor="0.05", linewidth=0.9),
        ax.bar([i + width / 2 for i in x], [p["cost_ratio"] for p in pairs], width,
               color=D1_COLOR, edgecolor="0.05", linewidth=0.9, hatch="//"),
    ]
    for group in groups:
        for bar in group:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.08,
                    f"{bar.get_height():.2f}x", ha="center", va="bottom",
                    fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels([p["label"] for p in pairs], fontsize=8.5)
    ax.set_ylabel("Ratio between the two workloads")
    ax.set_ylim(0.45, max(p["ca_ratio"] for p in pairs) * 6)
    ax.legend(handles=[
        Patch(facecolor=CA_COLOR, edgecolor="0.05", label="CA-predicted ratio"),
        Patch(facecolor=D1_COLOR, edgecolor="0.05", hatch="////",
              label="Measured miss-rate ratio"),
    ], loc="upper center", frameon=False, fontsize=8.5, ncol=2)
    ax.set_title("(b) Identical measured cost, up to 1273x apart in CA",
                 fontsize=10, pad=6)


def build_pairs(points: list[dict]) -> list[dict]:
    """Pick workload pairs that sit in the same cache tier but differ in CA."""
    by_d = {p["distinct"]: p for p in points}
    specs = [
        (768, 65536, "both L1-miss / L2-hit"),
        (98304, 1048576, "both L2-miss (RAM)"),
        (768, 1048576, "both L1-miss"),
    ]
    pairs = []
    for low, high, note in specs:
        if low not in by_d or high not in by_d:
            continue
        a, b = by_d[low], by_d[high]
        pairs.append({
            "label": f"{human_bytes(a['working_set'])} vs "
                     f"{human_bytes(b['working_set'])}\n{note}",
            "ca_ratio": a["ca"] / b["ca"],
            "cost_ratio": b["d1"] / a["d1"],
        })
    return pairs


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path,
                        default=root / "results/exp3_ca_saturation.csv")
    parser.add_argument("-o", "--output", type=Path,
                        default=root / "results/exp3_ca_saturation.png")
    args = parser.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 11,
        "axes.linewidth": 1.0,
        "hatch.linewidth": 1.0,
    })

    points = load_points(args.csv)
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12.2, 4.4),
                                     gridspec_kw={"width_ratios": [1.5, 1.0]})
    draw_panel_a(ax_a, points)
    draw_panel_b(ax_b, build_pairs(points))
    fig.tight_layout(pad=0.9)
    fig.savefig(args.output, dpi=220)
    fig.savefig(args.output.with_suffix(".pdf"))

    print(f"{'D':>8}{'WS':>10}{'tier':>6}{'CA':>13}{'L1 miss%':>10}{'L2 miss%':>10}")
    for p in points:
        print(f"{p['distinct']:>8}{human_bytes(p['working_set']):>10}"
              f"{tier(p['working_set']):>6}{p['ca']:>13.8f}"
              f"{p['d1']:>10.1f}{p['ll']:>10.1f}")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
