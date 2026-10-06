"""Specification tests for experiment 28: CAAS Algorithm 1 on experiment 27's sets (run from the c3 copy)."""
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import algorithm1 as a1
import ca_table
import deadline_big_caas_set
import deadline_big_set
import deadline_caas_set
import deadline_set
from chaser.locality.ca import ca_csrd

DESIGNS = ((deadline_caas_set, deadline_set), (deadline_big_caas_set, deadline_big_set))
FROZEN = HERE.parent.parent / 'calibration-v2/frozen-policies.json'


def tasks_of(module, load, cell, set_id, placement):
    return module.configuration(load, cell, set_id, placement)['tasks']


def strip(tasks):
    return [{k: v for k, v in t.items() if k != 'core'} for t in tasks]


def test_thresholds_and_core_groups_are_the_frozen_calibrated_policies():
    policies = json.loads(FROZEN.read_text())['policies']
    assert a1.POLICIES['caas'] == ('ca-csrd', policies['ca-csrd']['threshold'])
    assert a1.POLICIES['cls-a1-cal'] == ('cls', policies['cls']['threshold'])
    assert a1.POLICIES['cls-a1'] == ('cls', 0.5)
    assert a1.CORE_GROUPS.isolated == tuple(policies['ca-csrd']['cores']['isolated'])
    assert a1.CORE_GROUPS.non_isolated == tuple(policies['ca-csrd']['cores']['non_isolated'])


def test_ca_table_reads_caas_l1_csrd_affinity_per_task(tmp_path):
    case = tmp_path / 'cv00-low50/u045/s00/yarda'
    case.mkdir(parents=True)
    task = dict(task_id='task_job_t00', l1=dict(csrd_histogram={'0': 6, '2': 2}))
    (case / 't00.json').write_text(json.dumps(dict(tasks=[task])))
    table = ca_table.table(tmp_path)
    assert table['cases']['cv00-low50/u045/s00'] == {'t00': pytest.approx(8 / (8 + 4))}
    assert table['cases']['cv00-low50/u045/s00']['t00'] == ca_csrd(task)


@pytest.mark.parametrize('caas, base', DESIGNS)
def test_ca_table_covers_every_case_and_task_of_the_design(caas, base):
    cases = json.loads(caas.CA_TABLE.read_text())['cases']
    for h in base.HEAVINESS:
        for load in base.LOADS:
            for k in range(base.SETS):
                key = f'{h}/u{round(load * 100):03d}/s{k:02d}'
                assert set(cases[key]) == {f't{i:02d}' for i in range(base.task_count(k))}, key
                assert all(0 <= v <= 1 for v in cases[key].values())


@pytest.mark.parametrize('caas, base', DESIGNS)
def test_placements_are_wfd_and_the_three_algorithm1_variants(caas, base):
    assert caas.PLACEMENTS == ('wfd', 'caas', 'cls-a1', 'cls-a1-cal')
    assert caas.SEED_BASE == base.SEED_BASE and caas.LOADS == base.LOADS and caas.HEAVINESS == base.HEAVINESS


@pytest.mark.parametrize('caas, base', DESIGNS)
@pytest.mark.parametrize('set_id', (0, 7, 13))
def test_wfd_build_is_experiment_27s_configuration(caas, base, set_id):
    for h in base.HEAVINESS:
        load = base.LOADS[2]
        assert caas.configuration(load, h, set_id, 'wfd') == base.configuration(load, h, set_id, 'wfd')


@pytest.mark.parametrize('caas, base', DESIGNS)
@pytest.mark.parametrize('policy', a1.POLICIES)
def test_algorithm1_placements_differ_from_experiment_27_only_in_cores(caas, base, policy):
    for load in (base.LOADS[0], base.LOADS[-1]):
        assert strip(tasks_of(caas, load, base.HEAVINESS[1], 5, policy)) == strip(tasks_of(base, load, base.HEAVINESS[1], 5, 'wfd'))


@pytest.mark.parametrize('caas, base', DESIGNS)
@pytest.mark.parametrize('policy', a1.POLICIES)
def test_placeable_sets_isolate_exactly_the_tasks_at_or_below_the_threshold_on_core_0(caas, base, policy):
    kind, threshold = a1.POLICIES[policy]
    cases = json.loads(caas.CA_TABLE.read_text())['cases']
    checked = 0
    for load in (base.LOADS[0], base.LOADS[-1]):
        for k in range(base.SETS):
            config = caas.configuration(load, base.HEAVINESS[1], k, policy)
            if not config['high_load']['placeable']:
                continue
            ca = cases[f'{base.HEAVINESS[1]}/u{round(load * 100):03d}/s{k:02d}']
            for t in config['tasks']:
                scalar = ca[t['task_id']] if kind == 'ca-csrd' else t['cls_planned']
                assert (t['core'] == 0) == (scalar <= threshold), (load, k, t['task_id'])
            assert max(config['high_load']['core_u']) <= 1.0 + 1e-9
            checked += 1
    assert checked


def test_unplaceable_sets_are_flagged_and_still_give_every_task_a_core():
    cell, load = 'cv00-low50', max(deadline_set.LOADS)
    config = deadline_caas_set.configuration(load, cell, 2, 'cls-a1')
    low_u = sum(t['u_planned'] for t in config['tasks'] if t['cls_planned'] <= 0.5)
    assert low_u > 1.0
    hl = config['high_load']
    assert hl['placeable'] is False and hl['unplaced']
    assert all(t['core'] in range(4) for t in config['tasks'])


@pytest.mark.parametrize('caas, base', DESIGNS)
def test_workload_and_policy_ids_name_the_algorithm1_variant(caas, base):
    ids = {caas.configuration(base.LOADS[0], base.HEAVINESS[0], 0, p)['workload_id'] for p in caas.PLACEMENTS}
    assert len(ids) == len(caas.PLACEMENTS)
    assert caas.configuration(base.LOADS[0], base.HEAVINESS[0], 0, 'caas')['workload_id'].endswith('-caas-v1')
