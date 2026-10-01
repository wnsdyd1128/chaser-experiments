"""Specification of the CLS-distribution task-set generator."""

import pytest

from chaser.periodic.measurement import make_plan
import clsset

# Synthetic calibration: CLS rises with hot repeats; sweeps keep U fixed.
TABLE = [dict(hot_repeats=r, sweeps=s, cls=c) for r, s, c in (
    (1, 16, 0.07), (4, 10, 0.18), (16, 5, 0.42), (64, 2, 0.66), (192, 1, 0.88), (397, 1, 0.95))]


def test_quantize_picks_the_nearest_calibrated_cls_and_prefers_fewer_repeats_on_ties():
    assert clsset.quantize(0.40, TABLE)['hot_repeats'] == 16
    assert clsset.quantize(0.25, TABLE)['hot_repeats'] == 4
    assert clsset.quantize(0.99, TABLE)['hot_repeats'] == 397
    tie = [dict(hot_repeats=8, sweeps=4, cls=0.75), dict(hot_repeats=2, sweeps=9, cls=0.25)]
    assert clsset.quantize(0.5, tie)['hot_repeats'] == 2


def test_targets_are_seeded_bounded_and_constant_for_zero_cv():
    first = clsset.targets(0.5, 0.3, 7, 0.07, 0.95)
    assert first == clsset.targets(0.5, 0.3, 7, 0.07, 0.95)
    assert len(first) == clsset.TASKS
    assert all(0.07 <= v <= 0.95 and abs(v - 0.5) <= 3 * 0.3 * 0.5 + 1e-12 for v in first)
    assert clsset.targets(0.5, 0.0, 7, 0.07, 0.95) == [0.5] * clsset.TASKS


def test_zigzag_mixes_cls_ranks_and_grouped_keeps_neighbours_together():
    values = [0.9, 0.1, 0.5, 0.3, 0.7, 0.2, 0.8, 0.4, 0.6, 0.05, 0.95, 0.35, 0.45, 0.15, 0.25, 0.85]
    order = sorted(range(16), key=lambda i: (values[i], i))
    zig = clsset.zigzag(values)
    grouped = clsset.grouped(values)
    assert sorted(zig) == sorted(grouped) == sorted(list(range(4)) * 4)
    for group in range(4):
        members = order[4 * group:4 * group + 4]
        assert sorted(zig[i] for i in members) == [0, 1, 2, 3]
        assert {grouped[i] for i in members} == {group}


@pytest.mark.parametrize('period', clsset.PERIODS)
def test_placements_share_tasks_and_differ_only_in_cores(period):
    tables = {p: TABLE for p in clsset.PERIODS}
    for cv in clsset.CVS:
        for set_id in clsset.set_ids(cv)[:3]:
            zig = clsset.configuration(period, 0.5, cv, set_id, tables, 'zigzag')
            grp = clsset.configuration(period, 0.5, cv, set_id, tables, 'grouped')
            strip = lambda c: [{k: v for k, v in t.items() if k != 'core'} for t in c['tasks']]
            assert strip(zig) == strip(grp)
            assert [t['task_id'] for t in zig['tasks']] == [f't{i:02d}' for i in range(clsset.TASKS)]
            for config in (zig, grp):
                plans = [make_plan(config, a) for a in range(3)]
                assert plans[0]['warmup_jobs'] == plans[0]['measurement_jobs'] == 10 * clsset.TASKS
                assert all(t['period_ticks'] == period and t['pattern'] == 'hot-cold' for t in config['tasks'])


def test_task_order_follows_calibrated_cls_and_cv_zero_is_uniform():
    tables = {p: TABLE for p in clsset.PERIODS}
    config = clsset.configuration(20, 0.5, 0.3, 0, tables, 'zigzag')
    levels = [t['cls_calibrated'] for t in config['tasks']]
    assert levels == sorted(levels)
    flat = clsset.configuration(20, 0.5, 0.0, 0, tables, 'grouped')
    assert len({(t['hot_repeats'], t['sweeps']) for t in flat['tasks']}) == 1
