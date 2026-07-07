#!/usr/bin/env python3
"""Build RTEMS ML framework JSON from YARDA RDH and measured results."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = {"global": 0, "clustered": 1, "partitioned": 2}


def ca_from_profile(profile: dict) -> float:
    histogram = profile.get("histogram", {})
    weighted = sum(int(rd) * int(count) for rd, count in histogram.items())
    reuses = sum(int(count) for count in histogram.values())
    if reuses == 0:
        return 0.0
    return reuses / (reuses + weighted)


def ca_values_from_rdh(path: Path, block_filters: list[str]) -> list[float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    blocks = payload.get("blocks", [])
    if not blocks:
        return [ca_from_profile(payload.get("program", payload))]

    selected = []
    for block in blocks:
        name = block.get("name", "")
        if block_filters and not any(token in name for token in block_filters):
            continue
        selected.append(ca_from_profile(block["profile"]))
    if selected:
        return selected
    raise ValueError(f"no YARDA block matched filters: {block_filters}")


def load_u_values(path: Path | None, period_ns: float) -> list[float]:
    if path is None:
        return []

    by_task: dict[int, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("experiment") != "exp2":
                continue
            if row.get("case") != "ALONE":
                continue
            if row.get("metric") != "avg_ns" or not row.get("task"):
                continue
            try:
                by_task[int(row["task"])] = float(row["value"]) / period_ns
            except (KeyError, ValueError, ZeroDivisionError):
                continue
    return [by_task[idx] for idx in sorted(by_task)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rdh", action="append", required=True,
                        help="YARDA RDH JSON path. Blocks become task CA values.")
    parser.add_argument("--task-block", action="append", default=[],
                        help="Substring of block name to include as a task.")
    parser.add_argument("--results-csv", help="CSV from parse_results.py")
    parser.add_argument("--period-ns", type=float, default=100_000_000.0)
    parser.add_argument("--label", choices=sorted(LABELS),
                        help="Optional ground-truth label for training/eval data.")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    ca_values = []
    for item in args.rdh:
        ca_values.extend(ca_values_from_rdh(Path(item), args.task_block))
    u_values = load_u_values(Path(args.results_csv) if args.results_csv else None,
                             args.period_ns)

    tasks = []
    for idx, ca_value in enumerate(ca_values):
        u_value = u_values[idx] if idx < len(u_values) else 0.0
        tasks.append({"CA": ca_value, "U": u_value})

    sample = {"tasks": tasks}
    if args.label:
        sample["label"] = LABELS[args.label]
    dataset = [sample]
    Path(args.output).write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
