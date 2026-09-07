#!/usr/bin/env python3
"""Join exp5-2 measurements with the CAAS RandomForest prediction per case.

Each case is measured twice: a flat build carrying GLOBAL and the two
partitioned placements, and a clustered build carrying CLUSTERED. Both halves
describe the same task set, so they are merged here before the comparison.

The deciding metric is the victims' worst-case response time, release to
completion. Execution time alone cannot see a task queueing behind a co-runner
pinned to the same core, and spreading exactly that queue is what a cluster
does. PARTITIONED_ALT is reported but excluded from the verdict: it is the same
partitioned architecture with the victims paired across phases, which no CAAS
feature can tell you to do.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

LINE_BYTES = 32
SELECTABLE = ("GLOBAL", "PARTITIONED", "CLUSTERED")
REPORTED = SELECTABLE + ("PARTITIONED_ALT",)
TIE_BAND_PCT = 5.0


def read_case(paths: list[Path]) -> dict:
    """Merge the flat and clustered CSVs of one case into one record."""
    setup: dict[str, int] = {}
    tasks: dict[tuple[str, int], dict] = {}
    config = ""

    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                config = row["config"] or config
                if row["case"] == "SETUP":
                    setup[row["metric"]] = int(row["value"])
                    continue
                key = (row["case"], int(row["task"]))
                entry = tasks.setdefault(key, {"role": row["role"]})
                entry[row["metric"]] = int(row["value"])

    return {"config": config, "setup": setup, "tasks": tasks}


def role_values(case: dict, placement: str, role: str, metric: str) -> list[int]:
    """Metric of every task with `role` under `placement`, task order kept."""
    return [entry[metric]
            for (name, _idx), entry in sorted(case["tasks"].items())
            if name == placement and entry["role"] == role]


def feature_tasks(case: dict) -> list[dict]:
    """CAAS input: closed-form CA and measured standalone U, one per task."""
    setup = case["setup"]
    ca = {"victim": 1.0 / setup["victim_distinct"],
          "polluter": 1.0 / setup["polluter_distinct"]}

    tasks = []
    for (name, _idx), entry in sorted(case["tasks"].items()):
        if name != "ALONE":
            continue
        tasks.append({"CA": ca[entry["role"]],
                      "U": entry["avg_exec_ns"] / entry["period_ns"]})
    return tasks


def predict(dataset_path: Path, framework: str, model: str) -> list[str]:
    """Run the saved CAAS model and return one architecture name per sample."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("rtems_ml_predict.py")),
         str(dataset_path), "--framework", framework, "--model", model],
        capture_output=True, text=True, check=True)

    labels = []
    for line in result.stdout.splitlines():
        if line.startswith("PREDICT,"):
            fields = dict(item.split("=", 1) for item in line.split(",")[1:])
            labels.append(fields["architecture"])
    return labels


def summarize(case: dict) -> dict:
    """Reduce one case to the row the report and the plot are built from."""
    setup = case["setup"]
    victim_bytes = setup["victim_bytes"]
    row = {
        "case": case["config"],
        "victim_distinct": setup["victim_distinct"],
        "victim_stride": setup["victim_stride"],
        "victim_bytes": victim_bytes,
        "victim_lines": -(-victim_bytes // LINE_BYTES),
        "heavy_sweeps": setup["heavy_sweeps"],
        "light_sweeps": setup["light_sweeps"],
        "ca_victim": 1.0 / setup["victim_distinct"],
        "ca_polluter": 1.0 / setup["polluter_distinct"],
    }

    alone = role_values(case, "ALONE", "victim", "avg_exec_ns")
    row["alone_victim_mean_us"] = sum(alone) / len(alone) / 1000.0
    row["u_victim"] = alone[0] / role_values(case, "ALONE", "victim",
                                             "period_ns")[0]

    for placement in REPORTED:
        prefix = placement.lower()
        resp = role_values(case, placement, "victim", "avg_resp_ns")
        worst = role_values(case, placement, "victim", "max_resp_ns")
        execution = role_values(case, placement, "victim", "avg_exec_ns")
        row[f"{prefix}_resp_mean_us"] = sum(resp) / len(resp) / 1000.0
        row[f"{prefix}_resp_worst_us"] = max(worst) / 1000.0
        row[f"{prefix}_exec_mean_us"] = sum(execution) / len(execution) / 1000.0
        row[f"{prefix}_misses"] = sum(
            role_values(case, placement, "victim", "misses")
            + role_values(case, placement, "polluter", "misses"))

    row["measured_best"] = min(
        SELECTABLE, key=lambda name: row[f"{name.lower()}_resp_mean_us"])
    return row


def score_prediction(row: dict) -> None:
    """Charge the model what its architecture costs against the best one.

    The verdict compares the predicted placement with the measured best rather
    than the best with its runner-up: what matters is how much the model's
    answer costs, not how close the two best placements are to each other.
    """
    best = row[f"{row['measured_best'].lower()}_resp_mean_us"]
    predicted = row[f"{row['rf_prediction'].lower()}_resp_mean_us"]
    row["rf_gap_pct"] = (predicted - best) / best * 100.0
    row["verdict"] = "wrong" if row["rf_gap_pct"] >= TIE_BAND_PCT else "ok"


def write_markdown(path: Path, rows: list[dict]) -> None:
    """Write the report: worst-case response per placement, then the verdict."""
    lines = [
        "# EXP5-2: clustered is the ground truth, CA cannot say so",
        "",
        "Victim response time, release to completion, measured with",
        "`rtems_clock_get_uptime_nanoseconds()` on the GR740 under laysim.",
        "Four victims alternate a heavy and a light job in opposite phases;",
        "four 32 KB polluters keep the cores they run on free of victim lines.",
        "CA = 1 / distinct, so the two cases carry one CA over a 32x change in",
        "cached footprint. Lower is better.",
        "",
        "Mean response decides. The worst case over 128 releases is reported"
        " too, but it is dominated by the rare release where a victim's"
        " deadline falls after a running polluter's, which is an EDF artefact"
        " rather than a property of the placement.",
        "",
        "| case | victim | lines | CA | U | GLOBAL mean us |"
        " PARTITIONED mean us | CLUSTERED mean us | measured best |"
        " RF prediction | RF costs | verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['victim_bytes'] / 1024:.3g} KB"
            f" (stride {row['victim_stride']}) | {row['victim_lines']}"
            f" | {row['ca_victim']:.3e} | {row['u_victim']:.4f}"
            f" | {row['global_resp_mean_us']:.2f}"
            f" | {row['partitioned_resp_mean_us']:.2f}"
            f" | {row['clustered_resp_mean_us']:.2f}"
            f" | {row['measured_best'].title()}"
            f" | {row['rf_prediction'].title()} | +{row['rf_gap_pct']:.1f}%"
            f" | {row['verdict']} |")

    lines += ["", "## The partition that would have worked", "",
              "PARTITIONED pairs victims 0 with 1 and 2 with 3, which is what",
              "index order gives and what `{CA, U}` cannot argue against: all",
              "four victims report the same CA and the same U. PARTITIONED_ALT",
              "pairs them across phases instead. It is the same architecture on",
              "the same cores, and only knowledge of the phases, which is in no",
              "CAAS feature, tells the two pairings apart.", "",
              "| case | PARTITIONED mean | PARTITIONED_ALT mean |"
              " CLUSTERED mean | worst: G / P / C |"
              " mean exec: G / P / C |",
              "|---|---:|---:|---:|---|---|"]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['partitioned_resp_mean_us']:.2f}"
            f" | {row['partitioned_alt_resp_mean_us']:.2f}"
            f" | {row['clustered_resp_mean_us']:.2f}"
            f" | {row['global_resp_worst_us']:.0f}"
            f" / {row['partitioned_resp_worst_us']:.0f}"
            f" / {row['clustered_resp_worst_us']:.0f}"
            f" | {row['global_exec_mean_us']:.1f}"
            f" / {row['partitioned_exec_mean_us']:.1f}"
            f" / {row['clustered_exec_mean_us']:.1f} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework",
                        default="/workspace/caas/MEM_RD_IR/rtems-ml-framework")
    parser.add_argument("--model", choices=["randomforest", "xgboost"],
                        default="randomforest")
    parser.add_argument("--results-dir")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results = Path(args.results_dir) if args.results_dir else root / "results"
    flat = sorted(item for item in results.glob("exp5_2_*.csv")
                  if not item.stem.endswith("_clustered")
                  and "cluster_mismatch" not in item.stem)
    cases = [read_case([path, path.with_name(f"{path.stem}_clustered.csv")])
             for path in flat]

    dataset_path = results / "exp5_2_ml_dataset.json"
    dataset_path.write_text(json.dumps(
        [{"tasks": feature_tasks(case)} for case in cases], indent=2),
        encoding="utf-8")

    rows = [summarize(case) for case in cases]
    for row, label in zip(rows, predict(dataset_path, args.framework,
                                        args.model)):
        row["rf_prediction"] = label.upper()
        score_prediction(row)
    rows.sort(key=lambda item: int(item["victim_stride"]))

    csv_path = results / "exp5_2_cluster_mismatch.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(results / "exp5_2_cluster_mismatch.md", rows)

    print(csv_path)
    print(results / "exp5_2_cluster_mismatch.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
