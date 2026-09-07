#!/usr/bin/env python3
"""Run the CA mean-RD limitation experiment from concrete C workloads.

The experiment uses two C programs in exp4-ca-mean-rd:

* ca_all_l1_miss.c: every target reuse is separated by 2048 cache lines.
* ca_mostly_l1_hit.c: most target reuses are immediate, with a small large-RD tail.

YARDA computes the cache-line RDH and CA from the C source.  CASA simulates the
generated APE JSON and this script extracts object-level statistics for
global::target, so the gap arrays are treated as RD-construction filler rather
than the measured object.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKLOAD_DIR = ROOT / "exp4-ca-mean-rd"
RESULTS_DIR = ROOT / "results" / "ca_mean_rd_c_repro"
YARDA_ROOT = Path("/workspace/Yet-Another-Reuse-Distance-Analyzer")
CASA_ROOT = Path("/workspace/CASA")

WORKLOADS = (
    ("all_l1_miss", "All L1-miss", WORKLOAD_DIR / "ca_all_l1_miss.c"),
    ("mostly_l1_hit", "Mostly L1-hit", WORKLOAD_DIR / "ca_mostly_l1_hit.c"),
)


def run(command: list[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        subprocess.run(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )


def yarda_metrics(export_path: Path) -> dict[str, float | int | str]:
    data = json.loads(export_path.read_text())
    hist = {int(k): int(v) for k, v in data["program"]["histogram"].items()}
    total_reuses = int(data["program"]["total_reuses"])
    cold_misses = int(data["program"]["cold_misses"])
    weighted_rd = sum(rd * count for rd, count in hist.items())
    mean_rd = weighted_rd / total_reuses if total_reuses else 0.0
    ca = total_reuses / (total_reuses + weighted_rd) if total_reuses else 0.0
    rdh = " + ".join(f"RD={rd}: {count}" for rd, count in sorted(hist.items()))
    return {
        "rdh": rdh,
        "total_reuses": total_reuses,
        "cold_misses": cold_misses,
        "weighted_rd_sum": weighted_rd,
        "mean_rd": mean_rd,
        "ca": ca,
    }


def casa_target_metrics(objects_csv: Path) -> dict[str, float | int]:
    with objects_csv.open(newline="") as source:
        rows = list(csv.DictReader(source))
    target_rows = [row for row in rows if row["object"].endswith("::target")]
    if not target_rows:
        raise RuntimeError(f"target object not found in {objects_csv}")
    row = target_rows[0]
    accesses = int(row["accesses"])
    hits = int(row["hits"])
    misses = int(row["misses"])
    miss_rate = float(row["miss_rate"])
    # In both C workloads target misses are LLC hits by construction, so this
    # isolates the L1 behavior of the object under the same simple cost model.
    estimated_cycles = 1.0 + 10.0 * miss_rate
    return {
        "target_accesses": accesses,
        "target_hits": hits,
        "target_misses": misses,
        "target_l1_miss_rate": miss_rate,
        "target_estimated_cycles_per_access": estimated_cycles,
    }


def prepare_casa_input(ape_json: Path, output_path: Path) -> Path:
    """Ensure the generated APE JSON has an explicit analyze annotation.

    Some LLVM/plugin combinations preserve the function body but leave the
    schema-v2 `annotations` array empty even though `llvm.global.annotations`
    exists in the IR.  CASA intentionally filters by annotation, so the
    reproduction script makes the analyzed function explicit before simulation.
    """

    data = json.loads(ape_json.read_text())
    if isinstance(data, dict) and "functions" in data:
        for function in data["functions"]:
            if function.get("body"):
                annotations = set(function.get("annotations", []))
                annotations.add("yard.analyze")
                function["annotations"] = sorted(annotations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2))
    return output_path


def plot(csv_path: Path, out_dir: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    with csv_path.open(newline="") as source:
        rows = list(csv.DictReader(source))

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

    labels = [row["label"] for row in rows]
    colors = ["#DD8452", "#4C72B0"]
    x = np.arange(len(labels))

    fig, axes = plt.subplots(1, 3, figsize=(8.2, 3.0), constrained_layout=True)

    ca_scaled = [float(row["ca"]) * 1e4 for row in rows]
    axes[0].bar(x, ca_scaled, color=colors, edgecolor="black", linewidth=0.7)
    axes[0].set_ylabel(r"YARDA $CA$ ($\times 10^{-4}$)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=18, ha="right")
    axes[0].set_ylim(0, max(ca_scaled) * 1.25)
    for i, row in enumerate(rows):
        axes[0].text(
            i,
            ca_scaled[i] + max(ca_scaled) * 0.03,
            f"mean RD\n{float(row['mean_rd']):.0f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

    miss_rates = [float(row["target_l1_miss_rate"]) * 100.0 for row in rows]
    axes[1].bar(x, miss_rates, color=colors, edgecolor="black", linewidth=0.7)
    axes[1].set_ylabel("CASA target L1 miss rate (%)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=18, ha="right")
    axes[1].set_ylim(0, 112)
    for i, value in enumerate(miss_rates):
        axes[1].text(i, value + 2.0, f"{value:.1f}%", ha="center", va="bottom", fontsize=8.5)

    costs = [float(row["target_estimated_cycles_per_access"]) for row in rows]
    axes[2].bar(x, costs, color=colors, edgecolor="black", linewidth=0.7)
    axes[2].set_ylabel("Target estimated cycles/access")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=18, ha="right")
    axes[2].set_ylim(0, max(costs) * 1.25)
    for i, value in enumerate(costs):
        axes[2].text(i, value + 0.25, f"{value:.2f}", ha="center", va="bottom", fontsize=8.5)

    for ax in axes:
        ax.grid(True, axis="y", linestyle=":", linewidth=0.7, alpha=0.45)

    fig.savefig(out_dir / "ca_mean_rd_c_repro_metrics.png", dpi=300)
    fig.savefig(out_dir / "ca_mean_rd_c_repro_metrics.pdf")
    plt.close(fig)


def write_summary(path: Path, rows: list[dict[str, object]]) -> None:
    a, b = rows
    ca_rel = abs(float(a["ca"]) - float(b["ca"])) / float(a["ca"]) * 100.0
    miss_ratio = float(a["target_l1_miss_rate"]) / max(
        float(b["target_l1_miss_rate"]), 1e-12
    )
    cost_ratio = float(a["target_estimated_cycles_per_access"]) / float(
        b["target_estimated_cycles_per_access"]
    )
    path.write_text(
        "\n".join(
            [
                "# C Reproduction: CA Mean-RD Limitation",
                "",
                "| Workload | YARDA RDH | mean RD | CA | CASA target L1 miss rate | Target est. cycles/access |",
                "|---|---|---:|---:|---:|---:|",
                *[
                    "| {label} | {rdh} | {mean_rd:.3f} | {ca:.8f} | "
                    "{target_l1_miss_rate:.3f} | {target_estimated_cycles_per_access:.3f} |".format(
                        **row
                    )
                    for row in rows
                ],
                "",
                f"- Relative CA difference: `{ca_rel:.3f}%`",
                f"- Target L1 miss-rate ratio, All L1-miss / Mostly L1-hit: `{miss_ratio:.2f}x`",
                f"- Target estimated-cost ratio, All L1-miss / Mostly L1-hit: `{cost_ratio:.2f}x`",
                "",
                "The two C workloads have nearly the same YARDA CA because their",
                "weighted mean RD is similar.  CASA object-level simulation shows",
                "that the target object has very different L1 behavior.",
            ]
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--yarda-root", type=Path, default=YARDA_ROOT)
    parser.add_argument("--casa-root", type=Path, default=CASA_ROOT)
    args = parser.parse_args()

    out_dir = args.results_dir
    yarda_dir = out_dir / "yarda"
    casa_dir = out_dir / "casa"
    log_dir = out_dir / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    yarda_dir.mkdir(parents=True, exist_ok=True)
    casa_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for name, label, c_path in WORKLOADS:
        export_path = yarda_dir / f"{name}_unroll_rdh.json"
        run(
            [
                "python3",
                "backend/main.py",
                "--mode",
                "unroll",
                "--granularity",
                "cache-line",
                "--cache-line-size",
                "32",
                str(c_path),
                "--export",
                str(export_path),
            ],
            cwd=args.yarda_root,
            log_path=log_dir / f"{name}.yarda.log",
        )

        ape_json = c_path.with_name(f"{c_path.stem}_g_ape.json")
        casa_output = casa_dir / name
        if casa_output.exists():
            shutil.rmtree(casa_output)
        casa_input = prepare_casa_input(
            ape_json, out_dir / "casa_inputs" / f"{name}_ape_for_casa.json"
        )
        run(
            [
                str(args.casa_root / "build" / "casa"),
                "run",
                str(casa_input),
                "--cache",
                str(args.casa_root / "settings" / "cachegrind.yaml"),
                "--output",
                str(casa_output),
                "--quiet",
                "--no-color",
            ],
            cwd=args.casa_root,
            log_path=log_dir / f"{name}.casa.log",
        )
        object_files = sorted(casa_output.glob("*_objects.csv"))
        if not object_files:
            raise RuntimeError(f"CASA object CSV not found under {casa_output}")
        objects_csv = object_files[0]

        row: dict[str, object] = {
            "name": name,
            "label": label,
            "source": str(c_path),
        }
        row.update(yarda_metrics(export_path))
        row.update(casa_target_metrics(objects_csv))
        rows.append(row)

    csv_path = out_dir / "ca_mean_rd_c_repro.csv"
    with csv_path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    write_summary(out_dir / "ca_mean_rd_c_repro.md", rows)
    plot(csv_path, out_dir)

    print(csv_path)
    print(out_dir / "ca_mean_rd_c_repro.md")
    print(out_dir / "ca_mean_rd_c_repro_metrics.png")


if __name__ == "__main__":
    main()
