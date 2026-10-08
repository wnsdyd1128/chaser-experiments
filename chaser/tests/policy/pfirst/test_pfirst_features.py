"""Pre-run RF rows in chaser.policy.pfirst reproduce the experiment feature code (rf_devcheck, rf_candidates)."""
from pathlib import Path
import random
import sys

import pytest

from chaser.policy.pfirst import features, placement

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'artifacts/periodic/scheduler-comparison-v1/policy-mix'))
import rf_candidates as rc  # noqa: E402

PERIODS = (20, 24, 30, 40, 48, 60, 80)


def random_set(seed):
    rng = random.Random(seed)
    n = rng.randint(6, 18)
    tasks = []
    for _ in range(n):
        low = rng.random() < 0.3
        p_l1 = rng.uniform(0.05, 0.2) if low else rng.uniform(0.85, 0.95)
        p_mem = rng.uniform(0.0, 1 - p_l1) if low else rng.uniform(0, 0.03)
        tasks.append(dict(u=rng.uniform(0.03, 0.3), period=rng.choice(PERIODS), cls=rng.uniform(0.0, 0.5) if low else rng.uniform(0.85, 0.95),
                          rate=rng.uniform(8, 16) if low else rng.uniform(2, 6), working_set_kib=rng.choice((32.75, 768.03, 36.0)),
                          p_l1=p_l1, p_mem=p_mem))
    return tasks


def as_experiment(tasks, mapping):
    return [dict(u_planned=t['u'], period_ticks=t['period'], cls_planned=t['cls'], traffic_planned=t['rate'],
                 footprint_kib=t['working_set_kib'], p_l1=t['p_l1'], p_mem=t['p_mem'], core=c) for t, c in zip(tasks, mapping)]


@pytest.mark.parametrize('seed', range(30))
@pytest.mark.parametrize('candidate', ('ra-cgb', 'wfd', 'g', 'c13', 'c112'))
def test_rows_match_the_experiment_feature_code(seed, candidate):
    tasks = random_set(seed)
    mapping = placement.release_aware_grouped(tasks, seed) if candidate == 'ra-cgb' else placement.wfd(tasks)
    mine = dict(features.set_features(tasks), **features.candidate_features(tasks, mapping, candidate))
    exp = as_experiment(tasks, mapping)
    theirs = dict(rc.rd.set_features(exp), **rc.candidate_features(exp, candidate))
    for key, value in theirs.items():
        assert mine[key] == value, key


def test_memory_demand_counts_the_l1_misses_that_reach_memory_at_220_ns_each():
    t = dict(u=0.2, period=40, cls=0.13, rate=4.0, working_set_kib=2560.0, p_l1=0.13, p_mem=0.87)
    f = features.set_features([t])
    assert f['memory_demand'] == pytest.approx(0.2 * 4.0 * 0.87 / 0.87 / (1000 / 220))
    assert f['occupancy'] == pytest.approx(f['cache_demand'] + f['memory_demand'])


def test_row_follows_the_given_feature_order():
    tasks = random_set(0)
    names = ['occupancy', 'is_g', 'total_u']
    values = features.row(tasks, placement.wfd(tasks), 'g', names)
    assert values[1] == 1.0 and values[2] == pytest.approx(sum(t['u'] for t in tasks))
