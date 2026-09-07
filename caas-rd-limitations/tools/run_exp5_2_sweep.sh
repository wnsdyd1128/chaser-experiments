#!/bin/sh
# Build and run every exp5-2 case under laysim, then parse each log to CSV.
#
# A case is "name:distinct:stride" and fixes the victim access pattern; the
# polluters stay at 32 KB. Each case needs two binaries: the flat one carries
# GLOBAL and both partitioned placements, the clustered one carries CLUSTERED.
# They cannot share a binary because a processor belongs to one scheduler
# instance for the life of the system.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
EXP_DIR="$ROOT_DIR/exp5-2-ca-cluster-mismatch"
OUT_DIR=${OUT_DIR:-"$ROOT_DIR/results"}
BIN_DIR="$EXP_DIR/b-cases"

CASES=${CASES:-"CV128:128:32 CP128:128:1"}

mkdir -p "$BIN_DIR" "$OUT_DIR"

build_case() {
    name=$1
    distinct=$2
    stride=$3
    extra=$4
    suffix=$5

    make -C "$EXP_DIR" clean >/dev/null
    make -C "$EXP_DIR" EXP5C_DEFS="-DEXP5C_VICTIM_DISTINCT=$distinct \
-DEXP5C_VICTIM_STRIDE=$stride -DEXP5C_CASE_NAME='\"$name\"' $extra" >/dev/null
    cp "$EXP_DIR/b-gr740/exp5_2_ca_cluster_mismatch.exe" \
        "$BIN_DIR/$name$suffix.exe"
    echo "built $name$suffix (distinct=$distinct stride=$stride)"
}

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    distinct=$(echo "$spec" | cut -d: -f2)
    stride=$(echo "$spec" | cut -d: -f3)

    build_case "$name" "$distinct" "$stride" "" ""
    build_case "$name" "$distinct" "$stride" "-DEXP5C_CLUSTERED=1" "_clustered"
done

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    for suffix in "" "_clustered"; do
        script -q -c "laysim-gr740-cli -r -core0 $BIN_DIR/$name$suffix.exe" \
            /dev/null > "$OUT_DIR/exp5_2_$name$suffix.log" 2>&1 &
    done
done
wait

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    for suffix in "" "_clustered"; do
        "$SCRIPT_DIR/parse_results.py" "$OUT_DIR/exp5_2_$name$suffix.log" \
            -o "$OUT_DIR/exp5_2_$name$suffix.csv"
        echo "$OUT_DIR/exp5_2_$name$suffix.csv"
    done
done
