"""Specification tests for the random-baseline designs (run from the c3 copy, PYTHONPATH set)."""
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boundary_set
import clsspread_set
import conflictcls_set
import loadmem_set
import mix_set
from placement_lib import RANDOM_POLICIES
import rnd_boundary_set
import rnd_conflict_set
import rnd_loadmem_set
import rnd_mix_set
import rnd_smallmem_set
import rnd_spread_set
import rnd_taskcount_set
import smallmem_set
import taskcount_set

PAIRS = ((rnd_smallmem_set, smallmem_set), (rnd_taskcount_set, taskcount_set), (rnd_spread_set, clsspread_set),
         (rnd_loadmem_set, loadmem_set), (rnd_conflict_set, conflictcls_set), (rnd_boundary_set, boundary_set),
         (rnd_mix_set, mix_set))


@pytest.mark.parametrize('mine, base', PAIRS)
def test_random_designs_keep_the_base_sets_and_draw_only_random_placements(mine, base):
    assert mine.HEAVINESS and set(mine.HEAVINESS) <= set(base.HEAVINESS)
    assert mine.PLACEMENTS == ('wfd',) + RANDOM_POLICIES  # wfd is built for hl_run's isolated gate and yarda
    assert (mine.LOADS, mine.SETS, mine.SEED_BASE) == (base.LOADS, base.SETS, base.SEED_BASE)


@pytest.mark.parametrize('mine, base', PAIRS)
def test_random_placements_change_only_the_cores_of_the_base_task_sets(mine, base):
    cell, load = mine.HEAVINESS[0], mine.LOADS[-1]
    strip = lambda ts: [{k: v for k, v in t.items() if k != 'core'} for t in ts]
    reference = strip(base.configuration(load, cell, 3, 'wfd')['tasks'])
    for policy in RANDOM_POLICIES:
        assert strip(mine.configuration(load, cell, 3, policy)['tasks']) == reference
