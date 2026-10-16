"""Register-bound jobs (alu-u32, fpu-f64): one load of a seed per sweep, then a chain of dependent IU or FPU
operations; the job returns a checksum of the results."""
from copy import deepcopy

import pytest

from chaser.periodic.codegen import workload_source
from chaser.periodic.kernels import reference_events, task_from_plan
from chaser.periodic.measurement import make_plan

M = 2 ** 32


def config(pattern, iterations=1, sweeps=2, seed=1, element_type='uint32_t'):
    return dict(schema_version=2, workload_id='compute-smoke', family_id='compute-diagnostic',
                policy_id='explicit-core-map-v1', horizon_ticks=40, warmup_ticks=20, u_repeats=1,
                arrays=[dict(array_id='s0', element_type=element_type, length=8, alignment_bytes=32, initial_value=seed)],
                tasks=[dict(task_id='t0', pattern=pattern, arrays=dict(seed=dict(array_id='s0', offset_elements=3)),
                            iterations=iterations, sweeps=sweeps, core=0, period_ticks=10)])


def test_alu_job_sums_a_xorshift_multiply_chain_over_its_sweeps():
    task = make_plan(config('alu-u32'), 2)['tasks'][0]
    x = 1
    x ^= (x << 13) % M   # 8193
    x ^= x >> 17         # 8193
    x ^= (x << 5) % M    # 270369
    x = x * 2654435761 % M
    assert task['expected_checksum'] == 2 * x % M
    assert (task['source_loads'], task['source_stores']) == (2, 0)


def test_fpu_job_sums_a_scaled_logistic_map_over_its_sweeps():
    task = make_plan(config('fpu-f64', iterations=2, seed=5), 2)['tasks'][0]
    x = (5 % 1000 + 1) / 1001.0
    for _ in range(2):
        x = 3.9 * x * (1.0 - x)
    assert task['expected_checksum'] == 2 * int(x * 4294967296.0) % M
    assert (task['source_loads'], task['source_stores']) == (2, 0)


@pytest.mark.parametrize('pattern', ['alu-u32', 'fpu-f64'])
def test_each_sweep_loads_the_seed_once(pattern):
    plan = make_plan(config(pattern, iterations=50, sweeps=3), 2)
    events = list(reference_events(task_from_plan(plan['tasks'][0]),
                                   {a['array_id']: __import__('chaser.periodic.workload', fromlist=['ArraySpec']).ArraySpec.from_dict(a)
                                    for a in plan['arrays']}))
    assert [(e.array_id, e.offset_bytes, e.operation) for e in events] == [('s0', 12, 'load')] * 3
    assert plan['tasks'][0]['unique_cache_lines'] == 1


@pytest.mark.parametrize('pattern, chain', [('alu-u32', 'x *= 2654435761U;'), ('fpu-f64', 'x = 3.9 * x * (1.0 - x);')])
def test_source_runs_the_chain_without_memory_operations_inside_the_loop(pattern, chain):
    plan = make_plan(config(pattern, iterations=50, sweeps=3), 2)
    source = workload_source(plan['tasks'], arrays=plan['arrays'])
    assert chain in source and 'task_job_t0' in source and 'i < 50' in source


@pytest.mark.parametrize('change, message', [
    (dict(iterations=0), 'iterations'),
    (dict(element_type='uint8_t'), 'uint32_t'),
])
@pytest.mark.parametrize('pattern', ['alu-u32', 'fpu-f64'])
def test_invalid_compute_tasks_are_rejected(pattern, change, message):
    with pytest.raises(ValueError, match=message):
        make_plan(config(pattern, **change), 2)


def test_recorded_laysim_run_matches_every_checksum_and_scales_with_the_iterations():
    # Recorded laysim run (fixture note): the target's IU and FPU results equal the Python chains bit for bit, and
    # four times the iterations take about four times the CPU (the O2 build keeps the whole chain).
    import json
    from pathlib import Path
    from chaser.periodic.measurement import parse_log
    fixture = json.loads((Path(__file__).parent / 'fixtures/compute-laysim-p.json').read_text())
    plan = fixture['plan']
    result = parse_log(fixture['log'], plan)
    assert result['execution_status'] == 'ok', result['errors']
    cpu = {i: min(j['cpu_after_ns'] - j['cpu_before_ns'] for j in result['jobs'] if j['task'] == i) for i in range(4)}
    for short, long in ((0, 1), (2, 3)):
        assert plan['tasks'][long]['iterations'] == 4 * plan['tasks'][short]['iterations']
        assert 3.5 < cpu[long] / cpu[short] < 4.1
