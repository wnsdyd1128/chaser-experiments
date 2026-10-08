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
