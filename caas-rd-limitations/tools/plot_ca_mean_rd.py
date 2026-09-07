#!/usr/bin/env python3
"""Plot the CA mean-RD limitation: identical CA, eight-fold memory cost.

CA = 1 / (1 + mean RD) reads the reuse histogram only through its weighted
mean. Two workloads are built to share that mean exactly and to differ in
shape, so CA cannot separate them while the cache plainly does.

Input is the laysim RESULT CSV from exp4-ca-mean-rd, parsed by
tools/parse_results.py, plus exp3's sweep for the cost of a reuse distance.
Two standalone figures are written: the miss ratio curves, whose equal areas
are the shared mean CA reads, and the measured cost split into its non-memory
measured L1-resident baseline marked on it.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import plot_ca_saturation as saturation

GR740_L1_LINES = 16 * 1024 // 32
GR740_L2_LINES = 2 * 1024 * 1024 // 32
NS_PER_CYCLE = 4.0                      # GR740 at 250 MHz, per the laysim log

A_COLOR = "#3A6EA5"
B_COLOR = "#2E8B62"
CURVE_COLOR = "#3C3C3C"
FLOOR_COLOR = "#C7C7C7"
MEAN_COLOR = "#C44E52"


def load_cases(path: Path) -> dict[int, list[dict]]:
    """Group the measured cases by `repeats`, each sorted by working set.

    @return repeats -> cases, every case carrying its measured ns per load.
    """
    cases: dict[str, dict[str, int]] = defaultdict(dict)
    for row in csv.DictReader(path.open(encoding="utf-8")):
        if row.get("experiment") != "exp4":
            continue
        cases[row["case"]][row["metric"]] = int(row["value"])
    by_k: dict[int, list[dict]] = defaultdict(list)
    for m in cases.values():
        m["ns"] = m["avg_ns"] / m["accesses"]
        by_k[m["repeats"]].append(m)
    return {k: sorted(v, key=lambda m: m["distinct"]) for k, v in by_k.items()}


def mean_rd(case: dict) -> Fraction:
    """Exact weighted mean reuse distance of one case.

    Each address is read `repeats` times in a row and the cycle runs `cycles`
    times, so the histogram holds D*C*(k-1) reuses at RD = 0 and D*(C-1) at
    RD = D-1. The first cycle contributes no reuse, which is why this sits
    below the asymptotic (D-1)/k.
    """
    d, k, c = case["distinct"], case["repeats"], case["cycles"]
    return Fraction((d - 1) * (c - 1), k * c - 1)


def histogram(case: dict) -> dict[int, int]:
    """Reuse histogram of one case, as RD -> reuse count."""
    d, k, c = case["distinct"], case["repeats"], case["cycles"]
    hist = {d - 1: d * (c - 1)}
    if k > 1:
        hist[0] = d * c * (k - 1)
    return hist


def baseline(cases: list[dict]) -> float:
    """The L1-resident case of one workload: the same loop with no memory stall.

    sweep() issues the same instructions per load at every shift, so the two
    workloads share this cost and their measured times are directly comparable.
    Nothing is fitted or subtracted to compare them; this case is measured, and
    is used only to say how much of each time is memory.

    @return that case's nanoseconds per load.
    @pre Exactly one case of this workload fits inside L1.
    """
    fit = [c for c in cases if c["working_set_bytes"] < GR740_L1_LINES * 32]
    if len(fit) != 1:
        raise ValueError(f"expected one L1-resident case, found {len(fit)}")
    return fit[0]["ns"]


def stall_of_delta(cachegrind_csv: Path, ns_csv: Path):
    """exp3's measured memory stall as a function of reuse distance.

    exp3 swept a cyclic load-only loop whose every reuse sits at one distance,
    so its cases sample the cost of a reuse distance directly. Reusing that
    measurement keeps the cost curve an observation rather than a model.

    @return (deltas, cycles, lookup) with lookup(delta) the stall in cycles.
    """
    points = saturation.load_points(cachegrind_csv)
    ns = saturation.load_ns_per_access(ns_csv)
    for p in points:
        p["ns"] = ns[p["distinct"]]
    a, b = saturation.fit_floor(points)
    for p in points:
        p["stall"] = (p["ns"] - (a + b / p["distinct"])) / NS_PER_CYCLE

    deltas = [p["distinct"] - 1 for p in points]
    cycles = [p["stall"] for p in points]

    def lookup(delta):
        below = [c for d, c in zip(deltas, cycles) if d <= delta]
        return below[-1] if below else 0.0

    return deltas, cycles, lookup


def _paid(pairs, f):
    """Cost each workload actually pays: its reuse mass weighted by the curve."""
    out = {}
    for name, case, _ in pairs:
        hist = histogram(case)
        out[name[0]] = (sum(c * f(rd) for rd, c in hist.items())
                        / sum(hist.values()))
    return out


def _mrc_steps(case):
    """Survival curve S(delta) = P(reuse distance >= delta), as x/y vertices.

    Kept as a ratio rather than a percentage so that the area under the curve
    is the mean reuse distance itself, with no factor of 100 to explain away.
    """
    hist = histogram(case)
    total = sum(hist.values())
    xs, ys, surv = [0.0], [1.0], 1.0
    for rd, count in sorted(hist.items()):
        xs += [rd, rd]
        ys += [surv, surv - count / total]
        surv -= count / total
    return xs, ys, surv


def draw_mrc(fig, pairs, curve):
    """The miss ratio curve, whose area is the mean reuse distance CA reads.

    S(c) = P(delta >= c) is the miss rate of an LRU cache of c lines, and for a
    non-negative variable the integral of S is the mean. So the area under each
    curve is that workload's mean reuse distance, equal for the two by
    construction while the curves are nothing alike. Each area is labelled in
    place: two identical numbers inside two very differently shaped regions is
    the argument, and it needs no sentence in the middle of the figure.

    The axis is linear because the area reading only holds there; a log axis
    would distort the one property the figure rests on.
    """
    _, _, f = curve
    ax = fig.subplots()
    paid = _paid(pairs, f)
    mean = float(mean_rd(pairs[0][1]))
    # Everything is placed off the data, so retuning the workloads retunes the
    # figure with them instead of leaving it framed for the previous design.
    far = max(max(histogram(case)) for _, case, _ in pairs)
    right = far * 1.07
    area_text = f"area = mean $\\delta$ = {mean:.0f}"

    hits, misses = {}, []
    for (name, case, color), hatch, alpha in zip(pairs, (None, "///"), (.24, .32)):
        hist = histogram(case)
        total = sum(hist.values())
        # Measured, not the asymptotic 1/k: the first cycle fills the cache
        # without yielding a reuse, so the long distance is paid C-1 times
        # against C for RD = 0.
        hits[name[0]] = 100 * sum(c for rd, c in hist.items()
                                  if rd >= GR740_L1_LINES) / total
        xs, ys, surv = _mrc_steps(case)
        xs, ys = xs + [right], ys + [surv]
        ax.plot(xs, ys, color=color, lw=2.4, zorder=5)
        ax.fill_between(xs, 0, ys, color=color, alpha=alpha, hatch=hatch,
                        edgecolor=color, lw=0, zorder=2,
                        label=f"{name} $\\cdot$ {paid[name[0]]:.1f} cycles"
                              " of stall per reuse")
        misses.append(hits[name[0]])

    # Saying the area twice, once inside each shape, lets the reader compare
    # two numbers instead of parsing a claim.
    tail = hits[pairs[1][0][0]] / 100               # B's plateau height
    plate = dict(facecolor="white", edgecolor="none", alpha=.82,
                 boxstyle="round,pad=0.28")
    ax.text((GR740_L1_LINES + mean) / 2, (1 + tail) / 2, area_text, bbox=plate,
            fontsize=10.5, color=pairs[0][2], ha="center", va="center",
            rotation=90, zorder=6)
    ax.text((mean + far) / 2, tail / 2, area_text, fontsize=10.5, bbox=plate,
            color=pairs[1][2], ha="center", va="center", zorder=6)

    ax.axvline(GR740_L1_LINES, color="0.35", ls=":", lw=1.4, zorder=4)
    ax.text(GR740_L1_LINES, 1.055, "L1 capacity (512 lines)", fontsize=9.5,
            color="0.35",
            ha="center", va="bottom")
    ax.annotate("", xy=(GR740_L1_LINES, 1.005), xytext=(GR740_L1_LINES, 1.05),
                arrowprops=dict(arrowstyle="->", color="0.5", lw=1.0))
    for name, _, color in pairs:
        ax.plot([GR740_L1_LINES], [hits[name[0]] / 100], marker="o", ms=9,
                color=color, zorder=6, mec="white", mew=1.5)
    # A's leader runs along the top edge of its own block, never across it.
    ax.annotate("all of A's reuses fall beyond L1",
                xy=(mean * 0.99, 1.002), xytext=(mean * 1.10, 0.88),
                fontsize=10.5, color=pairs[0][2], ha="left", va="center",
                arrowprops=dict(arrowstyle="-", color=pairs[0][2], lw=1.0))
    ax.annotate(f"only {hits['B']:.1f}% of B's do",
                xy=(mean * 1.06, tail), xytext=(mean * 1.16, tail + 0.20),
                fontsize=10.5, color=pairs[1][2], ha="left", va="center",
                arrowprops=dict(arrowstyle="-", color=pairs[1][2], lw=1.0))

    ax.set_xlim(-right * 0.012, right)
    ax.set_ylim(0, 1.10)
    ax.set_yticks((0, 0.25, 0.5, 0.75, 1.0))
    ax.set_xlabel("Reuse distance $\\delta$,  equivalently LRU cache size in lines")
    ax.set_ylabel("Fraction of reuses at or\nbeyond this distance")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper right", frameon=False, fontsize=10.5,
              bbox_to_anchor=(1.0, 1.03))


def draw_cost(fig, pairs, bases, ca):
    """The two measured costs, with the shared L1-resident case marked.

    The bars are measured times, not derived ones. The baseline is measured
    too: it is the same loop run on a working set that fits in L1, so whatever
    stands above it is the memory cost and nothing has been fitted away.
    """
    ax = fig.subplots()
    x = list(range(len(pairs)))
    total = [case["ns"] / NS_PER_CYCLE for _, case, _ in pairs]
    base = sum(bases) / len(bases) / NS_PER_CYCLE
    above = [t - base for t in total]

    ax.bar(x, total, 0.46, color=[p[2] for p in pairs], edgecolor="0.15",
           linewidth=1.0, alpha=0.9)
    ax.axhline(base, color="0.25", ls="--", lw=1.5, zorder=4)
    ax.text(-0.52, base + 0.7, "same loop, working set inside L1: "
            f"{base:.1f} cycles", fontsize=9.5, color="0.25", va="bottom")

    for xi, tot, extra, (_, _, color) in zip(x, total, above, pairs):
        ax.annotate("", xy=(xi + 0.30, tot), xytext=(xi + 0.30, base),
                    arrowprops=dict(arrowstyle="<->", color=color, lw=1.3))
        ax.text(xi + 0.35, (tot + base) / 2, f"+{extra:.2f}\nmemory",
                fontsize=10, color=color, ha="left", va="center")
        ax.text(xi, tot + 0.6, f"{tot:.2f} cycles", ha="center", va="bottom",
                fontsize=11.5)

    ax.text(0.5, base * 0.55,
            f"{total[0] / total[1]:.2f}x measured,\n"
            f"{above[0] / above[1]:.2f}x on the memory part,\n"
            f"at CA = {ca:.2e} for both",
            ha="center", va="center", fontsize=11)

    ax.set_xticks(x)
    ax.set_xticklabels([p[0] for p in pairs], fontsize=10)
    ax.set_xlim(-0.62, len(pairs) - 0.22)
    ax.set_ylabel("Measured cycles per load")
    ax.set_ylim(0, max(total) * 1.20)
    ns = ax.secondary_yaxis("right", functions=(lambda c: c * NS_PER_CYCLE,
                                                lambda n: n / NS_PER_CYCLE))
    ns.set_ylabel("ns per load  (GR740 at 250 MHz)")
    for side in ("top",):
        ax.spines[side].set_visible(False)


def main() -> int:
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-caas-rd")
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path,
                        default=root / "results/exp4_time_domain.csv")
    parser.add_argument("--exp3-csv", type=Path,
                        default=root / "results/exp3_ca_saturation.csv")
    parser.add_argument("--exp3-ns-csv", type=Path,
                        default=root / "results/exp3_time_domain.csv")
    parser.add_argument("-o", "--output-dir", type=Path,
                        default=root / "results")
    parser.add_argument("--tag", default="",
                        help="suffix for the output filenames")
    args = parser.parse_args()

    by_k = load_cases(args.csv)
    if len(by_k) != 2:
        parser.error(f"expected two workloads in {args.csv}, found {len(by_k)}")

    pairs, bases = [], []
    for (k, cases), color in zip(sorted(by_k.items()), (A_COLOR, B_COLOR)):
        # Share the measured mass, so the legend and the annotations agree.
        hist = histogram(cases[-1])
        hit = 100 * sum(c for rd, c in hist.items()
                        if rd < GR740_L1_LINES) / sum(hist.values())
        label = ("A: all reuses beyond L1" if k == 1
                 else f"B: {hit:.1f}% of reuses at $\\delta$ = 0")
        pairs.append((label, cases[-1], color))
        bases.append(baseline(cases))

    means = [mean_rd(c) for _, c, _ in pairs]
    if means[0] != means[1]:
        parser.error(f"the two workloads must share a mean RD, got {means}")

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

    ca = 1 / (1 + float(means[0]))
    curve = stall_of_delta(args.exp3_csv, args.exp3_ns_csv)
    for name, size, draw in (
        ("exp4_mean_rd_mrc", (9.4, 3.9), lambda fig: draw_mrc(fig, pairs, curve)),
        ("exp4_mean_rd_cost", (6.4, 4.5),
         lambda fig: draw_cost(fig, pairs, bases, ca)),
    ):
        fig = plt.figure(figsize=size)
        draw(fig)
        fig.set_layout_engine("constrained")
        fig.savefig(args.output_dir / f"{name}{args.tag}.png", dpi=220)
        fig.savefig(args.output_dir / f"{name}{args.tag}.pdf")
        plt.close(fig)
        print(args.output_dir / f"{name}{args.tag}.png")

    print(f"\nmean RD {means[0]} and CA {ca:.10f}, identical for both\n")
    print(f"{'workload':>10}{'D':>8}{'k':>4}{'ns/load':>10}"
          f"{'L1 base':>10}{'memory ns':>11}{'memory cyc':>12}")
    for (label, case, _), b in zip(pairs, bases):
        print(f"{label[0]:>10}{case['distinct']:>8}{case['repeats']:>4}"
              f"{case['ns']:>10.3f}{b:>10.3f}{case['ns'] - b:>11.3f}"
              f"{(case['ns'] - b) / NS_PER_CYCLE:>12.2f}")
    print(f"\n  the two L1-resident cases agree to "
          f"{abs(bases[0] - bases[1]) / bases[0]:.3%}, which is what lets the "
          "measured times be compared directly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
