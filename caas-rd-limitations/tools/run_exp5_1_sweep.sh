#!/bin/sh
# Build and run every exp5 case under laysim, then parse each log to CSV.
#
# A case is "name:distinct:stride[:victims]" and fixes the victim access pattern
# and how many tasks of each role run; the polluters stay at 32 KB throughout.
# distinct alone sets CA = 1 / distinct, so the P and F members of a pair carry
# one CA over a 32x footprint change, and the victim count moves how many of
# them share a core under the partitioned placement.
#
# Cases run in parallel because laysim is single-threaded and each run is
# independent; set JOBS=1 to serialise.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
EXP_DIR="$ROOT_DIR/exp5-1-ca-arch-mismatch"
OUT_DIR=${OUT_DIR:-"$ROOT_DIR/results"}
BIN_DIR="$EXP_DIR/b-cases"

CASES=${CASES:-"\
P064:64:1 F064:64:32 \
P096:96:1 F096:96:32 \
P128:128:1 F128:128:32 \
P192:192:1 F192:192:32 \
P256:256:1 F256:256:32 \
F384:384:32 F768:768:32 \
P128T12:128:1:6 F128T12:128:32:6 \
P096T16:96:1:8 F096T16:96:32:8"}

mkdir -p "$BIN_DIR" "$OUT_DIR"

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    distinct=$(echo "$spec" | cut -d: -f2)
    stride=$(echo "$spec" | cut -d: -f3)
    victims=$(echo "$spec" | cut -d: -f4)
    victims=${victims:-4}

    make -C "$EXP_DIR" clean >/dev/null
    make -C "$EXP_DIR" EXP5_DEFS="-DEXP5_VICTIM_DISTINCT=$distinct \
-DEXP5_VICTIM_STRIDE=$stride -DEXP5_VICTIMS=$victims \
-DEXP5_POLLUTERS=$victims -DEXP5_CASE_NAME='\"$name\"'" >/dev/null
    cp "$EXP_DIR/b-gr740/exp5_ca_arch_mismatch.exe" "$BIN_DIR/$name.exe"
    echo "built $name (distinct=$distinct stride=$stride victims=$victims)"
done

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    script -q -c "laysim-gr740-cli -r -core0 $BIN_DIR/$name.exe" /dev/null \
        > "$OUT_DIR/exp5_1_$name.log" 2>&1 &
done
wait

for spec in $CASES; do
    name=$(echo "$spec" | cut -d: -f1)
    "$SCRIPT_DIR/parse_results.py" "$OUT_DIR/exp5_1_$name.log" \
        -o "$OUT_DIR/exp5_1_$name.csv"
    echo "$OUT_DIR/exp5_1_$name.csv"
done
