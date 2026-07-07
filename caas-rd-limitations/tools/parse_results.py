#!/usr/bin/env python3
"""Convert RTEMS RESULT lines to CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


FIELDS = ["experiment", "case", "task", "metric", "value"]


def parse_result_line(line: str) -> dict[str, str] | None:
    line = line.strip()
    if not line.startswith("RESULT,"):
        return None

    row: dict[str, str] = {}
    for item in line.split(",")[1:]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        row[key.strip()] = value.strip()
    return row


def iter_lines(path: str | None):
    if path is None or path == "-":
        yield from sys.stdin
        return
    with Path(path).open(encoding="utf-8") as handle:
        yield from handle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="laysim log path, or stdin if omitted")
    parser.add_argument("-o", "--output", help="CSV output path, default stdout")
    args = parser.parse_args()

    rows = []
    extra_fields: set[str] = set()
    for line in iter_lines(args.log):
        row = parse_result_line(line)
        if row is None:
            continue
        rows.append(row)
        extra_fields.update(row)

    fieldnames = FIELDS + sorted(extra_fields.difference(FIELDS))
    out = Path(args.output).open("w", newline="", encoding="utf-8") if args.output else sys.stdout
    with out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
