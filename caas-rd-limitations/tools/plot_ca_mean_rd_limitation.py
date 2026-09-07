#!/usr/bin/env python3
"""Visualize a mean-RD limitation of the CA metric.

This synthetic experiment constructs two reuse-distance histograms with nearly
the same weighted mean RD, and therefore nearly the same CA score:

    CA = T / (T + P) = 1 / (1 + mean_RD)

However, the two RDHs imply very different cache behavior when interpreted
against a concrete hierarchy.  The All L1-miss workload has every reuse beyond
L1, while the Mostly L1-hit workload has mostly L1-local reuses and a small
LLC-resident tail.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workload:
    name: str
    label: str
    histogram: dict[int, int]


def calculate_ca(histogram: dict[int, int]) -> tuple[int, int, float, float]:
    """Return T, P, mean_rd, CA for an RD histogram."""

    total_reuses = sum(histogram.values())
    weighted_rd = sum(rd * count for rd, count in histogram.items())
    mean_rd = weighted_rd / total_reuses if total_reuses else 0.0
    ca = total_reuses / (total_reuses + weighted_rd) if total_reuses else 0.0
    return total_reuses, weighted_rd, mean_rd, ca


def cache_metrics(
    histogram: dict[int, int],
    l1_lines: int,
    llc_lines: int,
    l1_hit_cycles: float,
    l1_miss_penalty: float,
    llc_miss_penalty: float,
) -> tuple[float, float, float]:
    """Estimate cache behavior from RD threshold interpretation.

    RD <= L1 capacity is interpreted as L1-local.  RD beyond L1 but within LLC
    is interpreted as an L1 miss/LLC hit.  RD beyond LLC is memory-level.
    """

    total_reuses = sum(histogram.values())
    if not total_reuses:
        return 0.0, 0.0, 0.0

    l1_misses = sum(count for rd, count in histogram.items() if rd > l1_lines)
    llc_misses = sum(count for rd, count in histogram.items() if rd > llc_lines)
    l1_miss_rate = l1_misses / total_reuses
    llc_miss_rate = llc_misses / total_reuses
    cycles_per_access = (
        l1_hit_cycles
        + l1_miss_penalty * l1_miss_rate
        + llc_miss_penalty * llc_miss_rate
    )
    return l1_miss_rate, llc_miss_rate, cycles_per_access


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    a, b = rows
    ca_delta = abs(float(a["ca"]) - float(b["ca"]))
    ca_rel = ca_delta / float(a["ca"]) * 100.0
    cost_ratio = float(a["estimated_cycles_per_access"]) / float(
        b["estimated_cycles_per_access"]
    )
    l1_ratio = float(a["l1_miss_rate"]) / max(float(b["l1_miss_rate"]), 1e-12)

    path.write_text(
        "\n".join(
            [
                "# CA Mean-RD Limitation Experiment",
                "",
                "This synthetic RDH experiment constructs two workloads with nearly",
                "identical `CA = 1 / (1 + mean_RD)`, but very different",
                "cache-level behavior.",
                "",
                "| Workload | RDH | mean RD | CA | L1 miss rate | Estimated cycles/access |",
                "|---|---|---:|---:|---:|---:|",
                *[
                    "| {label} | {rdh} | {mean_rd:.3f} | {ca:.8f} | "
                    "{l1_miss_rate:.3f} | {estimated_cycles_per_access:.3f} |".format(
                        **row
                    )
                    for row in rows
                ],
                "",
                f"- Relative CA difference: `{ca_rel:.3f}%`",
                f"- L1 miss-rate ratio, All L1-miss / Mostly L1-hit: `{l1_ratio:.2f}x`",
                f"- Estimated cost ratio, All L1-miss / Mostly L1-hit: `{cost_ratio:.2f}x`",
                "",
                "Interpretation:",
                "",
                "- `CA` is nearly the same because it only depends on the",
                "  weighted mean RD.",
                "- The All L1-miss workload has every reuse beyond L1, causing",
                "  persistent L1 misses.",
                "- The Mostly L1-hit workload has mostly RD=0 reuses and only a small",
                "  LLC-resident tail, so it is much more cache-friendly despite a",
                "  similar CA score.",
            ]
        )
        + "\n"
    )


def plot(results_dir: Path, rows: list[dict[str, object]], workloads: list[Workload]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9.5,
            "axes.linewidth": 1.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    colors = {
        "concentrated": "#DD8452",
        "tail_heavy": "#4C72B0",
    }

    # Figure 1: RDH shape.
    fig, ax = plt.subplots(figsize=(6.5, 3.4), constrained_layout=True)
    width_factor = {0: 0.0, 2048: -0.06, 32768: 0.06}
    for workload in workloads:
        xs = np.array(list(workload.histogram.keys()), dtype=float)
        ys = np.array(list(workload.histogram.values()), dtype=float)
        # Use pseudo-log-friendly x for RD=0.
        plot_xs = np.where(xs == 0, 1.0, xs)
        ax.scatter(
            plot_xs,
            ys,
            s=140,
            marker="o",
            color=colors[workload.name],
            edgecolor="black",
            linewidth=0.7,
            label=workload.label,
            zorder=3,
        )
        for x, plot_x, y in zip(xs, plot_xs, ys):
            ax.vlines(plot_x, 0, y, color=colors[workload.name], linewidth=2.2, alpha=0.85)
            ax.text(
                plot_x * (1.08 if x else 1.22),
                y + 24,
                f"{int(y)}",
                ha="left",
                va="bottom",
                fontsize=9,
                color="0.18",
            )

    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2048, 32768])
    ax.set_xticklabels(["0", "2048", "32768"])
    ax.set_ylim(0, 1080)
    ax.set_xlabel("Reuse distance (cache lines)")
    ax.set_ylabel("Reuse count")
    ax.grid(True, which="major", axis="both", linestyle=":", linewidth=0.7, alpha=0.45)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.53, 1.18),
        ncol=2,
        frameon=True,
        framealpha=0.95,
        edgecolor="0.85",
    )
    fig.savefig(results_dir / "ca_mean_rd_limitation_rdh.png", dpi=300)
    fig.savefig(results_dir / "ca_mean_rd_limitation_rdh.pdf")
    plt.close(fig)

    # Figure 2: same CA, different cache behavior.
    labels = [str(row["label"]) for row in rows]
    x = np.arange(len(labels))

    fig, axes = plt.subplots(1, 3, figsize=(8.2, 3.0), constrained_layout=True)
    bar_colors = [colors[str(row["name"])] for row in rows]

    ca_scaled = [float(row["ca"]) * 1e4 for row in rows]
    axes[0].bar(x, ca_scaled, color=bar_colors, edgecolor="black", linewidth=0.7)
    axes[0].set_ylabel(r"$CA$ ($\times 10^{-4}$)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=18, ha="right")
    for i, row in enumerate(rows):
        axes[0].text(
            i,
            ca_scaled[i] + 0.015,
            f"mean RD\n{float(row['mean_rd']):.0f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    axes[0].set_ylim(0, max(ca_scaled) * 1.23)

    l1_rates = [float(row["l1_miss_rate"]) * 100.0 for row in rows]
    axes[1].bar(x, l1_rates, color=bar_colors, edgecolor="black", linewidth=0.7)
    axes[1].set_ylabel("L1 miss rate (%)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=18, ha="right")
    for i, value in enumerate(l1_rates):
        axes[1].text(i, value + 2.0, f"{value:.1f}%", ha="center", va="bottom", fontsize=8.5)
    axes[1].set_ylim(0, 112)

    costs = [float(row["estimated_cycles_per_access"]) for row in rows]
    axes[2].bar(x, costs, color=bar_colors, edgecolor="black", linewidth=0.7)
    axes[2].set_ylabel("Estimated cycles/access")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=18, ha="right")
    for i, value in enumerate(costs):
        axes[2].text(i, value + 0.25, f"{value:.2f}", ha="center", va="bottom", fontsize=8.5)
    axes[2].set_ylim(0, max(costs) * 1.22)

    for ax in axes:
        ax.grid(True, axis="y", linestyle=":", linewidth=0.7, alpha=0.45)

    fig.savefig(results_dir / "ca_mean_rd_limitation_metrics.png", dpi=300)
    fig.savefig(results_dir / "ca_mean_rd_limitation_metrics.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results",
    )
    parser.add_argument("--l1-lines", type=int, default=1024)
    parser.add_argument("--llc-lines", type=int, default=65536)
    parser.add_argument("--l1-hit-cycles", type=float, default=1.0)
    parser.add_argument("--l1-miss-penalty", type=float, default=10.0)
    parser.add_argument("--llc-miss-penalty", type=float, default=40.0)
    args = parser.parse_args()

    workloads = [
        Workload(
            name="concentrated",
            label="All L1-miss",
            histogram={2048: 1000},
        ),
        Workload(
            name="tail_heavy",
            label="Mostly L1-hit",
            histogram={0: 937, 32768: 63},
        ),
    ]

    args.results_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for workload in workloads:
        total_reuses, weighted_rd, mean_rd, ca = calculate_ca(workload.histogram)
        l1_miss_rate, llc_miss_rate, cycles_per_access = cache_metrics(
            workload.histogram,
            args.l1_lines,
            args.llc_lines,
            args.l1_hit_cycles,
            args.l1_miss_penalty,
            args.llc_miss_penalty,
        )
        rows.append(
            {
                "name": workload.name,
                "label": workload.label,
                "rdh": " + ".join(
                    f"RD={rd}: {count}" for rd, count in sorted(workload.histogram.items())
                ),
                "total_reuses": total_reuses,
                "weighted_rd_sum": weighted_rd,
                "mean_rd": mean_rd,
                "ca": ca,
                "l1_miss_rate": l1_miss_rate,
                "llc_miss_rate": llc_miss_rate,
                "estimated_cycles_per_access": cycles_per_access,
            }
        )

    csv_path = args.results_dir / "ca_mean_rd_limitation.csv"
    with csv_path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    write_summary(args.results_dir / "ca_mean_rd_limitation.md", rows)
    plot(args.results_dir, rows, workloads)

    print(csv_path)
    print(args.results_dir / "ca_mean_rd_limitation.md")
    print(args.results_dir / "ca_mean_rd_limitation_rdh.png")
    print(args.results_dir / "ca_mean_rd_limitation_metrics.png")


if __name__ == "__main__":
    main()
