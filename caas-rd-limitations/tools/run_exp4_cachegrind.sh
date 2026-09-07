#!/bin/sh
# Measure the exp4 access patterns under cachegrind with the GR740 geometry.
#
# The laysim run reports what the two patterns cost in time; this run reports
# what the cache does with them, so the miss ratio next to the reuse-distance
# curve is an observation rather than only the LRU model's reading of the
# histogram. 16 KB L1 per core and 2 MB shared L2, both 4-way with 32 B lines.
#
# A case is "name:distinct:repeats" and mirrors one RTEMS case; cycles is
# derived so that every case issues the same number of accesses, which keeps
# the process startup traffic and the 1/cycles cold-miss share comparable.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
BIN="$ROOT_DIR/exp4-ca-mean-rd/b-native/mean_rd_sweep"
OUT=${OUT:-"$ROOT_DIR/results/exp4_cachegrind.csv"}

STRIDE=32
ACCESSES=${ACCESSES:-8388608}
CACHE_FLAGS="--I1=16384,4,32 --D1=16384,4,32 --LL=2097152,4,32"
CASES=${CASES:-"K1D1023:1023:1 K4D4095:4095:4"}

if [ ! -x "$BIN" ]; then
    echo "missing $BIN; run: make -C $ROOT_DIR/exp4-ca-mean-rd" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT")"
echo "case,distinct,repeats,cycles,working_set_bytes,accesses,d1_rd_miss_pct,ll_rd_miss_pct" > "$OUT"

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    distinct=$(echo "$spec" | cut -d: -f2)
    repeats=$(echo "$spec" | cut -d: -f3)
    cycles=$((ACCESSES / (distinct * repeats)))

    report=$(valgrind --tool=cachegrind $CACHE_FLAGS \
        --cachegrind-out-file=/dev/null "$BIN" "$distinct" "$repeats" "$cycles" 2>&1)
    d1=$(echo "$report" | sed -n 's/.*D1  miss rate: *\([0-9.]*\)%.*(\ *\([0-9.]*\)%.*/\2/p')
    ll=$(echo "$report" | sed -n 's/.*LLd miss rate: *\([0-9.]*\)%.*(\ *\([0-9.]*\)%.*/\2/p')
    echo "$name,$distinct,$repeats,$cycles,$((distinct * STRIDE)),$((distinct * repeats * cycles)),$d1,$ll" >> "$OUT"
    echo "  $name distinct=$distinct repeats=$repeats cycles=$cycles d1=$d1% ll=$ll%" >&2
done

echo "$OUT"
