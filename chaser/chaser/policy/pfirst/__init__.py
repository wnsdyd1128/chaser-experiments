"""CHASER P-first framework: affinity-based Partitioned placement and the pre-run check.

inputs     per-task values from the plan (U, period) and the YARDA (HARA) outputs (CLS, rates, working set)
placement  nominal Partitioned check, U-balanced WFD, balanced CLS grouping and release-aware search within it
features   the fixed-length rows of the frozen pre-run RF (set, cache, memory and candidate features)
decision   the frozen policy: CHASER placement, Global/Clustered fallback, rejected or deferred, plus the
           static D + M rule kept for comparison
The placement and the features reproduce the experiment scripts of scheduler-comparison-v1 (placement_lib,
rf_devcheck, rf_candidates, rf_occupancy) value for value; tests/policy/pfirst checks that.
"""
