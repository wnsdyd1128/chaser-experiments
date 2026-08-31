#!/bin/sh
# Sweep the exp3 working set and record cache miss rates under cachegrind.
#
# The cache geometry is forced to the GR740's on the command line, so the
# result describes that target rather than the host CPU the sweep runs on:
# 16 KB L1 per core and 2 MB shared L2, both 4-way with 32 B lines.
#
# Only measured quantities are written. CA is derived from `distinct` and
# `sweeps` at plot time so the closed form has a single definition.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
BIN="$ROOT_DIR/exp3-ca-metric/b-native/ca_sweep"
OUT=${OUT:-"$ROOT_DIR/results/exp3_ca_saturation.csv"}

# Must match CA_SWEEP_STRIDE in exp3-ca-metric/ca_sweep.c.
STRIDE=32

# Total accesses is held constant across cases so that process startup traffic
# and the 1/sweeps cold-miss share stay comparable between working sets.
ACCESSES=${ACCESSES:-8388608}

CACHE_FLAGS="--I1=16384,4,32 --D1=16384,4,32 --LL=2097152,4,32"
DISTINCT_LIST=${DISTINCT_LIST:-"128 256 384 512 768 1024 2048 8192 16384 \
49152 65536 98304 131072 262144 524288 1048576"}

if [ ! -x "$BIN" ]; then
    echo "missing $BIN; run: make -C $ROOT_DIR/exp3-ca-metric" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT")"
echo "distinct,working_set_bytes,sweeps,accesses,d1_rd_miss_pct,ll_rd_miss_pct" > "$OUT"

for distinct in $DISTINCT_LIST; do
    sweeps=$((ACCESSES / distinct))
    report=$(valgrind --tool=cachegrind $CACHE_FLAGS \
        --cachegrind-out-file=/dev/null "$BIN" "$distinct" "$sweeps" 2>&1)
    d1=$(echo "$report" | sed -n 's/.*D1  miss rate: *\([0-9.]*\)%.*(\ *\([0-9.]*\)%.*/\2/p')
    ll=$(echo "$report" | sed -n 's/.*LLd miss rate: *\([0-9.]*\)%.*(\ *\([0-9.]*\)%.*/\2/p')
    echo "$distinct,$((distinct * STRIDE)),$sweeps,$((distinct * sweeps)),$d1,$ll" >> "$OUT"
    echo "  distinct=$distinct sweeps=$sweeps d1=$d1% ll=$ll%" >&2
done

echo "$OUT"
