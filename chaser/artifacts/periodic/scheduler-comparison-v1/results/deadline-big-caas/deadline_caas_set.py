"""Experiment 28, 32 KiB type: CAAS Algorithm 1 on experiment 27's deadline-small sets.

Same tasks, sets and seeds as deadline_set; P runs on algorithm1's caas (CA-CSRD), cls-a1 (CLS,
threshold 0.5) and cls-a1-cal (CLS, calibrated threshold), so every run pairs with experiment 27's
results on the same case. CA-CSRD comes from ca_table.py over experiment 27's yarda analyses
(CA_TABLE). wfd is built (not run) for hl_run's isolated gate and pm_run's yarda pass.
"""
from deadline_set import *  # noqa: F401,F403  the base design's constants, sets and seeds
import deadline_set as _base

import algorithm1

CA_TABLE = HERE.parent / 'results/ca-csrd/deadline-small.json'  # noqa: F405
PLACEMENTS = ('wfd',) + tuple(algorithm1.POLICIES)


def configuration(load: float, heaviness: str, set_id: int, placement: str) -> dict:
    return algorithm1.configuration(_base, CA_TABLE, load, heaviness, set_id, placement)


def protocol_extra() -> dict:
    return dict(_base.protocol_extra(), algorithm1_policies=algorithm1.POLICIES, ca_table=str(CA_TABLE.name))
