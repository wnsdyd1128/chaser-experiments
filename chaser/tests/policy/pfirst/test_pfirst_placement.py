"""CHASER placement in chaser.policy.pfirst reproduces the experiment scripts and checks nominal capacity."""
from pathlib import Path
import random
import sys

import pytest

from chaser.policy.pfirst import placement

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'artifacts/periodic/scheduler-comparison-v1/policy-mix'))
import placement_lib  # noqa: E402  (stdlib-only experiment module)

PERIODS = (20, 24, 30, 40, 48, 60, 80, 120)


def random_set(seed):
    rng = random.Random(seed)
    n = rng.randint(6, 20)
    total = rng.uniform(1.2, 3.2)
    w = [rng.random() for _ in range(n)]
    return [dict(u=total * x / sum(w), period=rng.choice(PERIODS), cls=rng.choice((0.05, 0.13, 0.3, 0.6, 0.9, 0.93)))
            for x in w]


def items(tasks):
    return [placement_lib.Item(u=t['u'], period=t['period'], traffic=0.0, cls=t['cls']) for t in tasks]


@pytest.mark.parametrize('seed', range(40))
def test_placements_match_the_experiment_scripts(seed):
    tasks = random_set(seed)
    assert placement.wfd(tasks) == placement_lib.place('wfd', items(tasks), seed)
    assert placement.grouped_balanced(tasks) == placement_lib.place('cgb', items(tasks), seed)
    assert placement.release_aware_grouped(tasks, seed) == placement_lib.place('ra-cgb', items(tasks), seed)


def test_release_search_keeps_low_cls_tasks_on_the_group_cores():
    tasks = random_set(3)
    start, final = placement.grouped_balanced(tasks), placement.release_aware_grouped(tasks, 3)
    low = [i for i, t in enumerate(tasks) if t['cls'] <= placement.CLS_LOW]
    assert {final[i] for i in low} <= {start[i] for i in low}


def test_nominal_check_separates_feasible_proven_infeasible_and_unknown():
    assert placement.nominal([dict(u=0.4, period=40, cls=0.9)] * 6)['status'] == 'feasible'
    assert placement.nominal([dict(u=0.5, period=40, cls=0.9)] * 6)['status'] == 'unknown'  # WFD finds no witness
    assert placement.nominal([dict(u=0.97, period=40, cls=0.9)])['status'] == 'proven_infeasible'
    assert placement.nominal([dict(u=0.6, period=40, cls=0.9)] * 7)['status'] == 'proven_infeasible'
    assert placement.nominal([dict(u=0.9, period=40, cls=0.9)] * 4 + [dict(u=0.1, period=40, cls=0.9)])['status'] == 'unknown'


def test_validator_rejects_missing_tasks_unknown_cores_and_overloads():
    tasks = [dict(u=0.5, period=40, cls=0.9)] * 2
    assert placement.valid(tasks, [0, 1])
    assert not placement.valid(tasks, [0])
    assert not placement.valid(tasks, [0, 4])
    assert not placement.valid(tasks, [0, 0])


def test_low_affinity_needs_a_low_cls_and_a_memory_intensity_at_or_above_the_threshold():
    assert placement.low_affinity(dict(cls=0.48, mpki=67.0))
    assert placement.low_affinity(dict(cls=0.48, mpki=placement.MPKI_MIN))
    assert not placement.low_affinity(dict(cls=0.0, mpki=0.01))   # a register-bound job: two cold misses only
    assert not placement.low_affinity(dict(cls=0.9, mpki=67.0))
    assert placement.low_affinity(dict(cls=0.48))                  # without an instruction count: CLS alone
    assert placement.low_affinity(dict(cls=0.48, mpki=None))


def test_a_low_cls_task_with_negligible_memory_intensity_is_placed_like_a_high_affinity_task():
    tasks = [dict(u=u, period=p, cls=c) for u, p, c in
             ((0.3, 20, 0.45), (0.3, 40, 0.47), (0.2, 20, 0.9), (0.25, 40, 0.95), (0.2, 80, 0.9), (0.3, 20, 0.92))]
    register_bound = [dict(t, cls=0.0, mpki=0.01) if i == 2 else t for i, t in enumerate(tasks)]
    as_high = [dict(t, cls=1.0) if i == 2 else t for i, t in enumerate(tasks)]
    assert placement.grouped_balanced(register_bound) == placement.grouped_balanced(as_high)
    assert placement.release_aware_grouped(register_bound, 7) == placement.release_aware_grouped(as_high, 7)
