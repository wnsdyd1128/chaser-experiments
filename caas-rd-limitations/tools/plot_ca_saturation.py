#!/usr/bin/env python3
"""Plot the CA saturation limitation: linear-in-RD CA vs step-shaped cache cost.

The left axis is always CA. The right axis carries the measured cost, on either
of the two paths that measure it:

  --axis miss   cache miss rates from tools/run_cachegrind_sweep.sh
  --axis ns     average time per array access, from the laysim run of
                exp3-ca-metric via tools/parse_results.py
  --axis stall  the same time with the fitted non-memory floor removed, which
                is the axis closest to a memory cost

Every axis reads the cachegrind CSV, which carries the sweep parameters CA is
derived from; ns and stall additionally read the laysim CSV for the cost.

The denominator counts array accesses only: one per loop iteration, with the
loop's own stack traffic left out of it. The numerator is the whole loop body,
so the quotient averages every instruction of an iteration onto its one array
access and is not a memory latency -- see run_case() in
exp3-ca-metric/saturation_workload.c for the definition.

Each run writes two standalone figures: the saturation curve, and the
same-tier pair ratios with a "_ratios" suffix.
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
NS_COLOR = "#8172B2"
STALL_COLOR = "#937860"


def fit_floor(points: list[dict]) -> tuple[float, float]:
    """Fit the non-memory cost of one loop iteration, as a + b / distinct.

    Every case runs the same instruction sequence, so the cost that is not a
    memory stall is a constant per inner iteration plus the outer-loop cost,
    which is paid once per sweep and so scales as 1 / distinct per access.
    Fitting on the L1-resident cases isolates it: there the working set fits in
    L1 and no stall is left to confound the fit. The case whose working set is
    exactly the L1 size is excluded, as it already takes conflict misses.

    @param[in] points Cases carrying "ns", "distinct" and "working_set".
    @return (a, b) of floor(distinct) = a + b / distinct, in nanoseconds.
    @pre At least two cases sit strictly inside L1.
    """
    fit = [p for p in points if p["working_set"] < GR740_L1_BYTES]
    if len(fit) < 2:
        raise ValueError("need two or more cases strictly inside L1 to fit")
    n = len(fit)
    xs = [1 / p["distinct"] for p in fit]
    ys = [p["ns"] for p in fit]
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    return my - b * mx, b


def ca_closed_form(distinct: int) -> float:
    """CA of a cyclic sweep over `distinct` addresses.

    Each iteration issues one read, so every reuse of an address sees the other
    distinct - 1 addresses in between and the histogram holds the single point
    RD = distinct - 1. Substituting into CA = sum(r) / sum((delta + 1) * r)
    cancels the reuse count, leaving 1 / distinct independent of how many times
    the cycle repeats.
    """
    return 1 / distinct


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
            "ca": ca_closed_form(distinct),
        })
    return sorted(points, key=lambda item: item["distinct"])


def load_ns_per_access(path: Path) -> dict[int, float]:
    """Read the laysim RESULT CSV and derive time per access for each case.

    Input is tools/parse_results.py output over the exp3 laysim log, which holds
    one row per (case, metric). ns/access is derived here rather than printed by
    the RTEMS binary so that each measured quantity keeps a single definition.

    @return distinct -> ns per access, for every exp3 case in the log.
    """
    cases: dict[str, dict[str, int]] = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        if row.get("experiment") != "exp3":
            continue
        cases.setdefault(row["case"], {})[row["metric"]] = int(row["value"])
    return {c["distinct"]: c["avg_ns"] / c["accesses"] for c in cases.values()}


def tier(working_set: int) -> str:
    if working_set <= GR740_L1_BYTES:
        return "L1"
    if working_set <= GR740_L2_BYTES:
        return "L2"
    return "RAM"


def human_bytes(value: int) -> str:
    for unit, scale in (("MiB", 1 << 20), ("KiB", 1 << 10)):
        if value >= scale:
            size = value / scale
            return f"{size:.0f} {unit}" if size == int(size) else f"{size:.1f} {unit}"
    return f"{value} B"


def draw_saturation_curve(ax, points, axis):
    from matplotlib.ticker import FuncFormatter, LogLocator
    from matplotlib.transforms import blended_transform_factory

    # Reuse distance on x: it is the quantity CA is built from, and the axis the
    # claim is about. A secondary axis carries the working set in bytes so the
    # cache boundaries stay readable without applying the 32 B stride mentally.
    delta = [p["distinct"] - 1 for p in points]
    l1_d, l2_d = GR740_L1_BYTES // 32 - 1, GR740_L2_BYTES // 32 - 1
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlim(min(delta) * 0.7, max(delta) * 1.4)
    ax.axvspan(min(delta) * 0.7, l1_d, color="0.93", zorder=0)
    ax.axvspan(l2_d, max(delta) * 1.4, color="0.86", zorder=0)

    ca_line, = ax.plot(delta, [p["ca"] for p in points], marker="o", ms=5.5,
                       lw=1.7, color=CA_COLOR, zorder=3,
                       label="CA (address-based)")
    ax.set_xlabel("Reuse distance, $\\delta$")
    ax.set_ylabel("CA", color=CA_COLOR)
    ax.tick_params(axis="y", colors=CA_COLOR)

    top = ax.secondary_xaxis(
        "top", functions=(lambda x: (x + 1) * 32, lambda w: w / 32 - 1))
    top.set_xlabel("Working set", fontsize=9, labelpad=4)
    top.xaxis.set_major_locator(LogLocator(base=2, numticks=7))
    top.xaxis.set_major_formatter(FuncFormatter(lambda v, _: human_bytes(int(v))))
    top.tick_params(labelsize=8.5)

    twin = ax.twinx()
    if axis in ("ns", "stall"):
        key = "ns" if axis == "ns" else "stall"
        color = NS_COLOR if axis == "ns" else STALL_COLOR
        label = "Load-only loop (laysim GR740)"
        ylabel = ("Average time per array access (ns)" if axis == "ns"
                  else "Memory stall per array access (ns)")
        cost_line, = twin.plot(delta, [p[key] for p in points], marker="s",
                               ms=5.5, lw=1.7, ls="--", color=color, zorder=3,
                               label=label)
        twin.set_ylabel(ylabel)
        twin.set_ylim(min(0, min(p[key] for p in points)),
                      max(p[key] for p in points) * 1.22)
        cost_lines = [cost_line]
    else:
        d1_line, = twin.plot(delta, [p["d1"] for p in points], marker="s", ms=5.5,
                             lw=1.7, ls="--", color=D1_COLOR, zorder=3,
                             label="L1 read miss rate (cachegrind)")
        ll_line, = twin.plot(delta, [p["ll"] for p in points], marker="^", ms=5.5,
                             lw=1.7, ls="-.", color=LL_COLOR, zorder=3,
                             label="L2 read miss rate (cachegrind)")
        twin.set_ylabel("Read miss rate (%)")
        twin.set_ylim(-5, 118)
        cost_lines = [d1_line, ll_line]

    # Sits below the secondary axis; the size is on that axis, so name the level.
    label_pos = blended_transform_factory(twin.transData, twin.transAxes)
    for boundary, name in ((l1_d, "L1"), (l2_d, "L2")):
        ax.axvline(boundary, color="0.3", ls=":", lw=1.3, zorder=1)
        twin.text(boundary, 0.90, f" {name}", fontsize=9, color="0.15",
                  ha="left", va="top", transform=label_pos)

    handles = [ca_line] + cost_lines
    twin.legend(handles, [h.get_label() for h in handles], loc="lower left",
                frameon=False, fontsize=8.5, bbox_to_anchor=(0.02, 0.05))


def draw_pair_ratios(ax, pairs, axis):
    """Two answers to one question: how much worse is the larger workload?

    CA answers with CA_small / CA_large and the measurement with
    cost_large / cost_small, so both bars are the same quantity and the gap
    between them is the metric's error rather than a difference of definition.
    """
    from matplotlib.patches import Patch

    cost_color = {"ns": NS_COLOR, "stall": STALL_COLOR}.get(axis, D1_COLOR)
    width = 0.3
    x = list(range(len(pairs)))
    ax.set_yscale("log")
    # The 1x line needs no label: the axis is a slowdown and the bar values
    # are printed, so a note would only sit in front of a bar.
    ax.axhline(1.0, color="0.3", ls=":", lw=1.3)

    groups = [
        ax.bar([i - width / 2 for i in x], [p["ca_ratio"] for p in pairs], width,
               color=CA_COLOR, edgecolor="0.05", linewidth=0.9),
        ax.bar([i + width / 2 for i in x], [p["cost_ratio"] for p in pairs], width,
               color=cost_color, edgecolor="0.05", linewidth=0.9, hatch="//"),
    ]
    for group in groups:
        for bar in group:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.08,
                    f"{bar.get_height():.2f}$\\times$", ha="center",
                    va="bottom", fontsize=8.5)

    # The takeaway is neither bar on its own but how far apart they are.
    for index, pair in enumerate(pairs):
        overstatement = pair["ca_ratio"] / pair["cost_ratio"]
        ax.text(index, pair["ca_ratio"] * 2.0,
                f"CA overstates\nby {overstatement:,.0f}$\\times$",
                ha="center", va="bottom", fontsize=9, fontweight="bold",
                color=CA_COLOR)

    ax.set_xticks(x)
    ax.set_xticklabels([p["label"] for p in pairs], fontsize=8.5)
    ax.set_ylabel("Slowdown of the larger workload")
    ax.set_ylim(0.45, max(p["ca_ratio"] for p in pairs) * 14)
    cost_label = {"ns": "Measured time",
                  "stall": "Measured memory stall"}.get(
                      axis, "Measured miss rate")
    ax.legend(handles=[
        Patch(facecolor=CA_COLOR, edgecolor="0.05", label="CA prediction"),
        Patch(facecolor=cost_color, edgecolor="0.05", hatch="////",
              label=cost_label),
    ], loc="upper center", frameon=False, fontsize=8.5, ncol=2)


def build_pairs(points: list[dict], axis: str) -> list[dict]:
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
        cost_key = {"ns": "ns", "stall": "stall"}.get(axis, "d1")
        pairs.append({
            "label": f"{human_bytes(a['working_set'])} $\\rightarrow$ "
                     f"{human_bytes(b['working_set'])}\n{note}",
            "ca_ratio": a["ca"] / b["ca"],
            "cost_ratio": b[cost_key] / a[cost_key],
        })
    return pairs


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path,
                        default=root / "results/exp3_ca_saturation.csv")
    parser.add_argument("--axis", choices=("miss", "ns", "stall"),
                        default="miss",
                        help="right-axis cost: cachegrind miss rates, laysim "
                             "average time per array access, or that time with "
                             "the fitted non-memory floor removed "
                             "(default: miss)")
    parser.add_argument("--ns-csv", type=Path,
                        default=root / "results/exp3_time_domain.csv",
                        help="laysim RESULT CSV, read for --axis ns and stall")
    parser.add_argument("-o", "--output", type=Path,
                        help="default: results/exp3_ca_saturation[_ns|_stall].png")
    args = parser.parse_args()

    if args.output is None:
        suffix = "" if args.axis == "miss" else f"_{args.axis}"
        args.output = root / f"results/exp3_ca_saturation{suffix}.png"

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 11,
        "axes.linewidth": 1.0,
        "hatch.linewidth": 1.0,
    })

    points = load_points(args.csv)
    floor = None
    if args.axis in ("ns", "stall"):
        ns_by_d = load_ns_per_access(args.ns_csv)
        missing = [p["distinct"] for p in points if p["distinct"] not in ns_by_d]
        if missing:
            parser.error(f"{args.ns_csv} has no laysim case for D={missing}")
        for p in points:
            p["ns"] = ns_by_d[p["distinct"]]
    if args.axis == "stall":
        floor = fit_floor(points)
        for p in points:
            p["stall"] = p["ns"] - (floor[0] + floor[1] / p["distinct"])

    # Two standalone figures rather than one two-panel image: each is sized to
    # stand on its own in a paper, with the description left to the caption.
    ratio_path = args.output.with_name(
        f"{args.output.stem}_ratios{args.output.suffix}")
    for path, size, draw in (
        (args.output, (7.2, 4.3),
         lambda ax: draw_saturation_curve(ax, points, args.axis)),
        (ratio_path, (5.6, 4.3),
         lambda ax: draw_pair_ratios(ax, build_pairs(points, args.axis), args.axis)),
    ):
        fig, ax = plt.subplots(figsize=size)
        draw(ax)
        fig.tight_layout(pad=0.6)
        fig.savefig(path, dpi=220)
        fig.savefig(path.with_suffix(".pdf"))
        plt.close(fig)

    extra = [k for k in ("ns", "stall") if k in points[0]]
    if floor is not None:
        print(f"floor(D) = {floor[0]:.3f} + {floor[1]:.1f}/D ns, "
              "fitted on the L1-resident cases")
    print(f"{'D':>8}{'WS':>10}{'tier':>6}{'CA':>13}{'L1 miss%':>10}"
          f"{'L2 miss%':>10}" + "".join(f"{k:>11}" for k in extra))
    for p in points:
        print(f"{p['distinct']:>8}{human_bytes(p['working_set']):>10}"
              f"{tier(p['working_set']):>6}{p['ca']:>13.8f}"
              f"{p['d1']:>10.1f}{p['ll']:>10.1f}"
              + "".join(f"{p[k]:>11.3f}" for k in extra))
    print(args.output)
    print(ratio_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
