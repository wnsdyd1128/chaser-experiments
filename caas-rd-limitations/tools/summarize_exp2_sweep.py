#!/usr/bin/env python3
"""Summarize exp2 sweep CSVs with us/ms units."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ARCHS = ("GLOBAL", "CLUSTERED", "PARTITIONED")


def ns_to_us(value: int) -> float:
    return value / 1_000.0


def ns_to_ms(value: int) -> float:
    return value / 1_000_000.0


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def value(rows: list[dict[str, str]], case: str, metric: str, task: int | None = None) -> int | None:
    task_text = "" if task is None else str(task)
    for row in rows:
        if row.get("case") == case and row.get("metric") == metric and row.get("task", "") == task_text:
            return int(row["value"])
    return None


def task_count(rows: list[dict[str, str]]) -> int:
    tasks = {
        int(row["task"])
        for row in rows
        if row.get("case") == "ALONE" and row.get("metric") == "avg_ns" and row.get("task")
    }
    return max(tasks) + 1 if tasks else 0


def summarize_one(path: Path) -> dict:
    rows = read_rows(path)
    n_tasks = task_count(rows)
    result = {"name": path.stem, "task_count": n_tasks, "architectures": []}
    for arch in ARCHS:
        avg_values = [value(rows, arch, "avg_ns", idx) or 0 for idx in range(n_tasks)]
        max_values = [value(rows, arch, "max_ns", idx) or 0 for idx in range(n_tasks)]
        misses = [value(rows, arch, "misses", idx) or 0 for idx in range(n_tasks)]
        result["architectures"].append({
            "architecture": arch,
            "elapsed_ns": value(rows, arch, "elapsed_ns") or 0,
            "mean_job_avg_ns": round(sum(avg_values) / len(avg_values)) if avg_values else 0,
            "worst_job_avg_ns": max(avg_values) if avg_values else 0,
            "worst_job_max_ns": max(max_values) if max_values else 0,
            "total_misses": sum(misses),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    args = parser.parse_args()

    summaries = [summarize_one(path) for path in args.csv]
    lines = ["# EXP2 Sweep Summary", ""]
    for summary in summaries:
        no_miss = [item for item in summary["architectures"] if item["total_misses"] == 0]
        best = min(no_miss, key=lambda item: item["worst_job_avg_ns"]) if no_miss else None
        lines.append(f"## {summary['name']}")
        lines.append("")
        lines.append(f"Tasks: `{summary['task_count']}`")
        lines.append("")
        lines.append("| architecture | elapsed_ms | mean_job_avg_us | worst_job_avg_us | worst_job_max_us | misses |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for item in summary["architectures"]:
            lines.append(
                "| {architecture} | {elapsed_ms:.3f} | {mean_us:.3f} | {worst_avg_us:.3f} | "
                "{worst_max_us:.3f} | {total_misses} |".format(
                    architecture=item["architecture"],
                    elapsed_ms=ns_to_ms(item["elapsed_ns"]),
                    mean_us=ns_to_us(item["mean_job_avg_ns"]),
                    worst_avg_us=ns_to_us(item["worst_job_avg_ns"]),
                    worst_max_us=ns_to_us(item["worst_job_max_ns"]),
                    total_misses=item["total_misses"],
                )
            )
        lines.append("")
        if best:
            lines.append(f"Best no-miss architecture by worst job avg time: `{best['architecture']}`.")
        else:
            lines.append("No architecture finished without deadline misses.")
        lines.append("")
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
