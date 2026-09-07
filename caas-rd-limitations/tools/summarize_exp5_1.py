#!/usr/bin/env python3
"""Join exp5-1 measurements with the CAAS RandomForest prediction per case.

Each case contributes one CAAS sample: eight standalone `{CA, U}` pairs, with
CA taken from the closed form of the cyclic sweep (CA = 1 / distinct, the exp3
identity) and U from the measured ALONE job time over the period. The saved
model is called through tools/rtems_ml_predict.py, so the prediction path is
the one exp2 uses.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

LINE_BYTES = 32
ARCHITECTURES = ("GLOBAL", "PARTITIONED")

# Both architectures run the same eight jobs on the same four cores, so a gap
# this small is a placement detail rather than an architecture preference. Runs
# are deterministic under laysim, so the band is not a noise allowance.
TIE_BAND_PCT = 5.0


def is_case_csv(path: Path) -> bool:
    """True for a parse_results.py output, false for a summary written here."""
    with path.open(encoding="utf-8") as handle:
        return handle.readline().startswith("experiment,case,task,metric,value")


def read_case(path: Path) -> dict:
    """Load one parsed laysim CSV into setup values and per-task metrics."""
    setup: dict[str, int] = {}
    tasks: dict[tuple[str, int], dict] = {}
    config = path.stem.replace("exp5_1_", "")

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = int(row["value"])
            if row["case"] == "SETUP":
                setup[row["metric"]] = value
                continue
            key = (row["case"], int(row["task"]))
            entry = tasks.setdefault(key, {"role": row["role"]})
            entry[row["metric"]] = value

    return {"config": config, "setup": setup, "tasks": tasks}


def role_values(case: dict, architecture: str, role: str, metric: str) -> list[int]:
    """Metric of every task with `role` under `architecture`, task order kept."""
    return [entry[metric]
            for (arch, _idx), entry in sorted(case["tasks"].items())
            if arch == architecture and entry["role"] == role]


def feature_tasks(case: dict) -> list[dict]:
    """CAAS input: closed-form CA and measured standalone U, one per task."""
    setup = case["setup"]
    ca = {"victim": 1.0 / setup["victim_distinct"],
          "polluter": 1.0 / setup["polluter_distinct"]}

    tasks = []
    for (arch, _idx), entry in sorted(case["tasks"].items()):
        if arch != "ALONE":
            continue
        tasks.append({"CA": ca[entry["role"]],
                      "U": entry["avg_ns"] / entry["period_ns"]})
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
        "victims": setup["victims"],
        "polluters": setup["polluters"],
        "victim_distinct": setup["victim_distinct"],
        "victim_stride": setup["victim_stride"],
        "victim_bytes": victim_bytes,
        "victim_lines": -(-victim_bytes // LINE_BYTES),
        "ca_victim": 1.0 / setup["victim_distinct"],
        "ca_polluter": 1.0 / setup["polluter_distinct"],
    }

    alone = role_values(case, "ALONE", "victim", "avg_ns")
    row["alone_victim_mean_us"] = sum(alone) / len(alone) / 1000.0
    row["u_victim"] = alone[0] / role_values(case, "ALONE", "victim", "period_ns")[0]

    for architecture in ARCHITECTURES:
        prefix = architecture.lower()
        victim = role_values(case, architecture, "victim", "avg_ns")
        polluter = role_values(case, architecture, "polluter", "avg_ns")
        row[f"{prefix}_victim_mean_us"] = sum(victim) / len(victim) / 1000.0
        row[f"{prefix}_victim_worst_us"] = max(victim) / 1000.0
        row[f"{prefix}_polluter_mean_us"] = sum(polluter) / len(polluter) / 1000.0
        row[f"{prefix}_set_mean_us"] = (sum(victim) + sum(polluter)) / (
            len(victim) + len(polluter)) / 1000.0
        row[f"{prefix}_set_worst_us"] = max(victim + polluter) / 1000.0
        row[f"{prefix}_misses"] = sum(
            role_values(case, architecture, "victim", "misses")
            + role_values(case, architecture, "polluter", "misses"))

    for axis in ("victim_mean", "victim_worst", "polluter_mean",
                 "set_mean", "set_worst"):
        globally = row[f"global_{axis}_us"]
        partitioned = row[f"partitioned_{axis}_us"]
        row[f"delta_{axis}_pct"] = (partitioned - globally) / globally * 100.0

    for axis, key in (("victim_mean", "measured_best"),
                      ("set_mean", "measured_best_set")):
        delta = row[f"delta_{axis}_pct"]
        if abs(delta) < TIE_BAND_PCT:
            row[key] = "TIE"
        else:
            row[key] = "PARTITIONED" if delta < 0 else "GLOBAL"
    return row


def same_ca_pairs(rows: list[dict]) -> list[tuple[dict, dict]]:
    """Case pairs sharing CA, U and task counts: where the claim is decided."""
    by_key: dict[tuple, list[dict]] = {}
    for row in rows:
        by_key.setdefault((row["ca_victim"], row["victims"]), []).append(row)
    return [(group[0], group[1]) for group in by_key.values() if len(group) == 2]


def score_prediction(row: dict) -> None:
    """Charge the model what its architecture costs against the better one.

    The verdict reads that cost rather than the sign of the difference: a
    placement the model missed by a percent is not a scheduling mistake.
    """
    best = min(row["global_victim_mean_us"], row["partitioned_victim_mean_us"])
    predicted = row[f"{row['rf_prediction'].lower()}_victim_mean_us"]
    row["rf_gap_pct"] = (predicted - best) / best * 100.0
    row["verdict"] = "wrong" if row["rf_gap_pct"] >= TIE_BAND_PCT else "ok"


def write_markdown(path: Path, rows: list[dict]) -> None:
    """Write the report table, pairing cases that share one CA."""
    lines = [
        "# EXP5-1: CA counts addresses, the cache counts lines",
        "",
        "Victim job time measured with `rtems_clock_get_uptime_nanoseconds()`",
        "on the GR740 under laysim. Every case runs four victims and four 32 KB",
        "polluters; only the victim access pattern changes. CA = 1 / distinct,",
        "so cases sharing `distinct` share CA exactly while their stride moves",
        "the footprint. Lower job time is better.",
        "",
        "| case | victim | lines | tasks | CA | U | GLOBAL mean us |"
        " PART mean us | delta | measured best | RF prediction | RF costs |"
        " verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for row in rows:
        verdict = row["verdict"]
        lines.append(
            f"| {row['case']} | {row['victim_bytes'] / 1024:.3g} KB"
            f" (stride {row['victim_stride']}) | {row['victim_lines']}"
            f" | {row['victims'] + row['polluters']}"
            f" | {row['ca_victim']:.3e} | {row['u_victim']:.4f}"
            f" | {row['global_victim_mean_us']:.2f}"
            f" | {row['partitioned_victim_mean_us']:.2f}"
            f" | {row['delta_victim_mean_pct']:+.1f}%"
            f" | {row['measured_best'].title()}"
            f" | {row['rf_prediction'].title()} | +{row['rf_gap_pct']:.1f}%"
            f" | {verdict} |")

    lines += ["", "## Whole task set", "",
              "The verdict above reads the four victims, the tasks whose reuse"
              " partitioning is meant to protect. Counting all eight tasks"
              " instead, PARTITIONED wins everywhere: confining the polluters"
              " to two cores halves the shared-L2 pressure they put on each"
              " other, which no CAAS feature reports either.", "",
              "| case | GLOBAL set mean us | PART set mean us | delta |"
              " polluter delta | set best |",
              "|---|---:|---:|---:|---:|---|"]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['global_set_mean_us']:.2f}"
            f" | {row['partitioned_set_mean_us']:.2f}"
            f" | {row['delta_set_mean_pct']:+.1f}%"
            f" | {row['delta_polluter_mean_pct']:+.1f}%"
            f" | {row['measured_best_set']} |")

    lines += ["", "## Cases that share one CA", "",
              "CA and U are what CAAS reads; the pair members differ only in"
              " stride, which the metric does not see.", "",
              "| CA | case | victim | U | measured best | delta |",
              "|---:|---|---:|---:|---|---:|"]
    for left, right in same_ca_pairs(rows):
        for row in (left, right):
            lines.append(
                f"| {row['ca_victim']:.3e} | {row['case']}"
                f" | {row['victim_bytes'] / 1024:.3g} KB | {row['u_victim']:.4f}"
                f" | {row['measured_best'].title()}"
                f" | {row['delta_victim_mean_pct']:+.1f}% |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="*", help="parsed exp5 case CSVs")
    parser.add_argument("--framework",
                        default="/workspace/caas/MEM_RD_IR/rtems-ml-framework")
    parser.add_argument("--model", choices=["randomforest", "xgboost"],
                        default="randomforest")
    parser.add_argument("--results-dir")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results = Path(args.results_dir) if args.results_dir else root / "results"
    paths = ([Path(item) for item in args.csv] if args.csv
             else sorted(item for item in results.glob("exp5_1_*.csv")
                         if is_case_csv(item)))
    cases = [read_case(path) for path in paths]

    dataset_path = results / "exp5_1_ml_dataset.json"
    dataset_path.write_text(json.dumps(
        [{"tasks": feature_tasks(case)} for case in cases], indent=2),
        encoding="utf-8")

    rows = [summarize(case) for case in cases]
    for row, label in zip(rows, predict(dataset_path, args.framework, args.model)):
        row["rf_prediction"] = label.upper()
        score_prediction(row)
    rows.sort(key=lambda item: (item["victims"], item["victim_distinct"],
                                item["victim_stride"]))

    csv_path = results / "exp5_1_arch_mismatch.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(results / "exp5_1_arch_mismatch.md", rows)

    print(csv_path)
    print(results / "exp5_1_arch_mismatch.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
