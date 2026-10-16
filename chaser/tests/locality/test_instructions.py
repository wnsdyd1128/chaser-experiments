"""Static per-job IR instruction counts from the APE map extraction (chaser.locality.instructions)."""
import pytest

from chaser.locality.instructions import job_ir_counts


def block(executions, opcodes, calls=()):
    return dict(executions=executions, opcodes=opcodes, calls=[dict(callee=c, inline=True) for c in calls])


def ape(*functions):
    return dict(functions=[dict(function=name, ir_instructions=dict(basis='map-extraction-ir', blocks=blocks))
                           for name, blocks in functions])


def test_a_job_counts_each_blocks_opcodes_times_its_executions_and_each_inlined_call():
    extraction = ape(('task_job_t0', [block(1, {'br': 1}), block(3, {'icmp': 1, 'br': 1}),
                                      block(2, {'add': 1, 'br': 1}, calls=['kernel_t0'])]),
                     ('kernel_t0', [block(1, {'br': 1}), block(4, {'load': 1, 'xor': 2, 'store': 1})]))
    # root: 1 + 3 x 2 + 2 x 2 = 11; each kernel call: 1 + 4 x 4 = 17 instructions and 4 x 2 = 8 memory operations
    assert job_ir_counts(extraction, 'task_job_t0') == (11 + 2 * 17, 2 * 8)


def test_calls_to_functions_outside_the_extraction_add_nothing():
    extraction = ape(('task_job_t0', [block(5, {'load': 1, 'call': 1}, calls=['memcpy'])]))
    assert job_ir_counts(extraction, 'task_job_t0') == (10, 5)


def test_a_job_reaching_a_function_without_constant_loop_counts_has_no_count():
    # YARDA marks such functions unsupported (e.g. a triangular loop): 'IR loop execution count is not constant'.
    extraction = ape(('task_job_t0', [block(2, {'br': 1}, calls=['kernel_t0'])]))
    extraction['functions'].append(dict(function='kernel_t0', ir_instructions=dict(
        basis='map-extraction-ir', status='unsupported', reason='IR loop execution count is not constant')))
    assert job_ir_counts(extraction, 'task_job_t0') is None


def test_a_missing_root_is_rejected():
    with pytest.raises(ValueError, match='task_job_t1'):
        job_ir_counts(ape(('task_job_t0', [block(1, {'br': 1})])), 'task_job_t1')


SDK = __import__('pathlib').Path('/opt/rtems/6')


@pytest.mark.skipif(not (SDK / 'bin/sparc-rtems6-gcc').exists() or __import__('shutil').which('clang-14') is None,
                    reason='requires the RTEMS SDK and clang-14')
def test_the_periodic_analysis_records_each_jobs_ir_instructions_over_its_segments(tmp_path):
    import json
    from chaser.periodic.analysis import analyze
    from chaser.periodic.build import prepare
    config = dict(schema_version=2, workload_id='ir-smoke', family_id='ir-diagnostic', policy_id='explicit-core-map-v1',
                  horizon_ticks=40, warmup_ticks=20, u_repeats=1,
                  arrays=[dict(array_id=f'r{i}', element_type='uint32_t', length=64, alignment_bytes=32, initial_value=3)
                          for i in range(2)],
                  tasks=[dict(task_id=f't{i}', pattern='cyclic', arrays=dict(input=dict(array_id=f'r{i}', offset_elements=0)),
                              distinct=16, stride_bytes=4, sweeps=5, core=i, period_ticks=10) for i in range(2)])
    config['tasks'][0].update(suspend_ticks=2, suspend_after_sweeps=2)
    prepare(config, tmp_path / 'prepared')
    cases = analyze(tmp_path / 'prepared')['cases']
    for task_id, case in cases.items():
        counts = [job_ir_counts(json.loads((tmp_path / f'prepared/analysis/{s}.ape.json').read_text()), 'task_job_' + s)
                  for s in case.get('segments', [task_id])]
        assert case['ir_instructions'] == sum(c[0] for c in counts) > 0
        assert sum(c[1] for c in counts) == case['modeled_accesses']  # IR loads and stores are HARA's accesses
