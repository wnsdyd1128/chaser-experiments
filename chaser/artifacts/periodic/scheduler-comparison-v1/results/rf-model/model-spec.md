# Frozen pre-run RF (experiment 43)

calibration **isotonic**, tau 0.8, 11733 rows, 28 features, model 66.9 MB
model SHA-256 `ec847c8755efcff2ebb57f53e7b7c251eee6e049367dffc8e4b56fece75b8f36`, prediction fingerprint `6d67762a2e4105d027b73944ad3ff265d877144951680fe831a465983715da21`

| calibration | held-out Brier | held-out AUC (all rows) | P-row AUC (all) | decision at tau: accepted met / false accept / false reject / saved / wrong switch |
|---|---:|---:|---:|---|
| none | 0.0337 | 0.9908 | 0.9909 | 1222 / 6 / 121 / 4 / 0 |
| isotonic | 0.0318 | 0.9905 | 0.9908 | 1223 / 8 / 118 / 4 / 0 |

## Feature importance (frozen model)

- occupancy: 0.295
- cache_demand: 0.143
- weighted_one_minus_cls: 0.135
- low_affinity_u: 0.106
- memory_demand: 0.103
- working_set_over_l2: 0.070
- total_u: 0.024
- max_working_set_kib: 0.023
- max_domain_u: 0.020
- max_group_core_u: 0.011
- effective_group_core_u: 0.010
- period_cv: 0.010
- t0_peak: 0.009
- max_u: 0.008
- u_cv: 0.006
- release_crowding: 0.006
- group_cores: 0.005
- other_u_on_group_cores: 0.004
- tasks: 0.004
- distinct_periods: 0.003
- is_c13: 0.001
- is_g: 0.001
- is_ra-cgb: 0.001
- is_cgb: 0.001
- is_wfd: 0.001
- is_c112: 0.001
- heavy_tasks: 0.000
- is_ra-cgk: 0.000
