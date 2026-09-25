"""Independent U and timing-only labels are required at the dataset boundary."""

from copy import deepcopy
import json
import pytest

from chaser.dataset.builder import Workload, freeze_split
from chaser.periodic.measurement import digest
from chaser.periodic.dataset import characterize, to_measurement, verify_frozen_inputs
from chaser.dataset.splits import taskset_signature
from tools.rtems_smoke import file_hash, write_json
from test_periodic import evidence


def batch(plan, *, mode=0):
    rows = []
    for run in range(plan['u_repeats']):
        rows.append(dict(run_id=str(run), plan_hash=plan['plan_hash'],
                         mode=mode, trace=False, empty=False, execution_status='ok',
                         elf_hash='a' * 64, log_hash='b' * 64, tet_ns=7000, tat_ns=12000,
                         jobs=[dict(task=mode - 1, job=j, cpu_before_ns=1000,
                                    cpu_after_ns=8000)
                               for j in range(plan['tasks'][mode - 1]['job_count'])]))
    return rows


def test_utilization_uses_all_independent_jobs_and_their_period():
    plan, _ = evidence()
    batches = [batch(plan, mode=i + 1) for i in range(len(plan['tasks']))]
    result = characterize(plan, batches)
    assert result['utilization'] == {'a': 0.0007, 'b': 0.00035}
    assert result['utilization_source'] == 'measured-run-median-v3'


@pytest.mark.parametrize('failure', ['missing_run', 'duplicate', 'failed', 'concurrent',
                                     'trace', 'empty', 'elf', 'missing_job'])
def test_utilization_rejects_incomparable_or_incomplete_measurements(failure):
    plan, _ = evidence()
    batches = [batch(plan, mode=i + 1) for i in range(len(plan['tasks']))]
    if failure == 'missing_run': batches[0].pop()
    if failure == 'duplicate': batches[0][1] = deepcopy(batches[0][0])
    if failure == 'failed': batches[0][0]['execution_status'] = 'failed'
    if failure == 'concurrent': batches[0][0]['mode'] = 0
    if failure == 'trace': batches[0][0]['trace'] = True
    if failure == 'empty': batches[0][0]['empty'] = True
    if failure == 'elf': batches[0][0]['elf_hash'] = 'different'
    if failure == 'missing_job': batches[0][0]['jobs'].pop()
    with pytest.raises(ValueError):
        characterize(plan, batches)


@pytest.mark.parametrize('field,value', [('trace', True), ('empty', True), ('mode', 1)])
def test_diagnostic_runs_cannot_become_timing_labels(field, value):
    plan, _ = evidence()
    row = batch(plan)[0]
    row[field] = value
    with pytest.raises(ValueError):
        to_measurement(plan, row)


def test_failed_run_keeps_its_identity_without_valid_label_metrics():
    plan, _ = evidence()
    row = batch(plan)[0]
    row['execution_status'] = 'failed'
    m = to_measurement(plan, row)
    assert m.execution_status == 'failed'
    assert m.tet is None and m.tat is None
    assert m.allocator_id == 'pilot-explicit-v1'


def test_frozen_dataset_inputs_verify_without_candidate_generator(tmp_path):
    frozen = tmp_path / 'frozen'
    configs = frozen / 'source/configs'
    configs.mkdir(parents=True)
    members, workloads = [], []
    for index in range(3):
        name = f'w{index}'
        config = dict(workload_id=name, family_id='source', policy_id='reference',
                      horizon_ticks=40, tasks=[dict(task_id='t0', core=0,
                                                   sweeps=index + 1, period_ticks=20)])
        write_json(configs / f'{name}.json', config)
        signature = taskset_signature(config)
        members.append(dict(workload_id=name, family_id='source',
                            input_signature=signature, configuration_hash=digest(config)))
        workloads.append(Workload(name, 'source', {}, 'pending', signature))
    split = freeze_split(frozen / 'split.json', workloads, seed=7)
    for row in members:
        row['split_group'] = split['assignments'][row['workload_id']]
    write_json(frozen / 'population.json', dict(workloads=members))
    write_json(frozen / 'summary.json', dict(candidate_workloads=3,
        workload_counts={group: list(split['assignments'].values()).count(group)
                         for group in ('train', 'validation', 'test')}))
    files = {str(path.relative_to(frozen)): file_hash(path)
             for path in frozen.rglob('*') if path.is_file()}
    write_json(frozen / 'manifest.json', dict(files=files))
    assert verify_frozen_inputs(frozen)['candidate_workloads'] == 3

    changed = dict(config)
    changed['tasks'] = [dict(config['tasks'][0], sweeps=99)]
    write_json(configs / 'w2.json', changed)
    manifest = json.loads((frozen / 'manifest.json').read_text())
    manifest['files']['source/configs/w2.json'] = file_hash(configs / 'w2.json')
    write_json(frozen / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='Frozen configuration'):
        verify_frozen_inputs(frozen)
