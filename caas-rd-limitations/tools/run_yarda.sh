#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
YARDA_DIR=${YARDA_DIR:-/workspace/Yet-Another-Reuse-Distance-Analyzer}
OUT_DIR=${OUT_DIR:-"$ROOT_DIR/results/yarda"}

mkdir -p "$OUT_DIR"

python3 "$YARDA_DIR/backend/main.py" \
  "$ROOT_DIR/exp1-cache-hierarchy/exp1_workload.c" \
  --mode unroll \
  --granularity cache-line \
  --export "$OUT_DIR/exp1_yarda_workload_unroll_rdh.json"

python3 "$YARDA_DIR/backend/main.py" \
  "$ROOT_DIR/exp2-task-interference/exp2_workload.c" \
  --mode unroll \
  --granularity cache-line \
  --export "$OUT_DIR/exp2_yarda_workload_unroll_rdh.json"
