import copy
import json
from pathlib import Path
import subprocess

import pytest

from chaser.s1.evaluation import evaluate_task

ROOT = Path(__file__).resolve().parents[1]


def arguments(tmp_path, case='packed'):
    ape = json.loads((ROOT / f'rtems/baseline/build/{case}.ape.json').read_text())
    ape['functions'][0]['body'][0]['bound'] = 3
    path = tmp_path / 'input.ape.json'
    path.write_text(json.dumps(ape))
    return dict(task_id='chaser_' + case, ape=path,
                elf=ROOT / f'rtems/baseline/build/{case}.exe',
                source=ROOT / 'rtems/baseline/workload.c', cache=ROOT / 'rtems/baseline/cache.yaml',
                executable=ROOT / 'rtems/baseline/build/yarda/backend/yarda_cpp',
                output_dir=tmp_path / 'evaluation', max_source_accesses=100,
                max_line_references=100, max_cumulative_loop_iterations=100, timeout=10)


@pytest.mark.parametrize('case,counts', [('packed', [47, 0, 1]), ('spread', [40, 0, 8]),
                                        ('conflict', [24, 16, 8])])
def test_actual_cpp_same_linked_stream_and_reference(tmp_path, case, counts):
    args = arguments(tmp_path, case)
    result = evaluate_task(**args)
    assert result['status'] == 'ok'
    assert result['reference']['counts'] == counts
    assert result['csrd']['counts'] == counts
    assert result['csrd']['error']['max_absolute_error'] == 0
    assert result['global_rd']['counts'] == ([47, 0, 1] if case == 'packed' else [40, 0, 8])
    assert result['global_rd']['error']['mae'] == pytest.approx(2 / 9 if case == 'conflict' else 0)
    assert result['validation_scope'] == 'cache-decisions-on-yarda-emitted-linked-stream'
    assert result['execution_validation'] == 'not-performed'
    assert len(result['stream_sha256']) == 64
    assert len(result['runs']) == 2
    assert all(r['wall_seconds'] >= 0 and r['started_at'] for r in result['runs'])
    assert json.loads((args['output_dir'] / 'comparison.json').read_text()) == result
    with pytest.raises(FileExistsError):
        evaluate_task(**args)


@pytest.mark.parametrize('damage', ['truncated', 'address', 'order', 'coverage', 'hash', 'model', 'counts'])
def test_bad_artifacts_are_preserved_as_failure(tmp_path, monkeypatch, damage):
    args = arguments(tmp_path)
    actual_run = subprocess.run

    def alter(argv, **kwargs):
        result = actual_run(argv, **kwargs)
        result_path = Path(argv[argv.index('--export') + 1])
        events_path = Path(argv[argv.index('--export-events') + 1])
        if result_path.name != 'global.json':
            return result
        data = json.loads(result_path.read_text())
        events = json.loads(events_path.read_text())
        if damage == 'truncated':
            events['events_truncated'] = True
        elif damage == 'address':
            events['events'][0]['linked_address'] += 32
        elif damage == 'order':
            events['events'][1]['source_access_ordinal'] = 0
        elif damage == 'coverage':
            data['tasks'][0]['coverage']['excluded_opaque_call_sites'] = 1
        elif damage == 'hash':
            data['inputs']['elf_sha256'] = 'wrong'
        elif damage == 'model':
            data['address_basis'] = 'synthetic'
        else:
            data['tasks'][0]['l1_first_hit_count'] -= 1
        result_path.write_text(json.dumps(data))
        events_path.write_text(json.dumps(events))
        return result

    monkeypatch.setattr(subprocess, 'run', alter)
    with pytest.raises(ValueError):
        evaluate_task(**args)
    out = args['output_dir']
    assert (out / 'global.events.json').exists()
    assert not (out / 'comparison.json').exists()
    assert json.loads((out / 'failure.json').read_text())['status'] == 'failed'


def test_reference_disagreement_is_a_reported_result(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    from chaser.locality.cache_reference import FirstHits
    monkeypatch.setattr('chaser.s1.evaluation.simulate', lambda *args: FirstHits(0, 0, 48))
    result = evaluate_task(**args)
    assert result['status'] == 'mismatch'
    assert result['csrd']['error']['max_absolute_error'] == pytest.approx(47 / 48)
    assert (args['output_dir'] / 'comparison.json').exists()


def test_limits_failure_keeps_raw_log(tmp_path):
    args = arguments(tmp_path)
    args['max_line_references'] = 1
    with pytest.raises(subprocess.CalledProcessError):
        evaluate_task(**args)
    assert (args['output_dir'] / 'actual.log').read_text()
    assert (args['output_dir'] / 'failure.json').exists()


def test_timeout_keeps_failure_record(tmp_path, monkeypatch):
    args = arguments(tmp_path)

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs['timeout'])

    monkeypatch.setattr(subprocess, 'run', timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        evaluate_task(**args)
    failure = json.loads((args['output_dir'] / 'failure.json').read_text())
    assert failure['runs'][0]['timed_out']
    assert (args['output_dir'] / 'actual.log').exists()


def test_source_mutation_is_rejected(tmp_path, monkeypatch):
    args = arguments(tmp_path)
    source = tmp_path / 'source.c'
    source.write_text(args['source'].read_text())
    args['source'] = source
    actual_run = subprocess.run

    def alter(argv, **kwargs):
        result = actual_run(argv, **kwargs)
        source.write_text('changed')
        return result

    monkeypatch.setattr(subprocess, 'run', alter)
    with pytest.raises(ValueError, match='changed'):
        evaluate_task(**args)
    assert not (args['output_dir'] / 'comparison.json').exists()


def test_multi_task_input_rejected_before_output(tmp_path):
    args = arguments(tmp_path)
    data = json.loads(args['ape'].read_text())
    data['functions'].append(copy.deepcopy(data['functions'][0]))
    args['ape'].write_text(json.dumps(data))
    with pytest.raises(ValueError, match='one matching'):
        evaluate_task(**args)
    assert not args['output_dir'].exists()


def test_cross_line_events_are_not_expanded_twice(tmp_path):
    args = arguments(tmp_path, 'spread')
    ape = json.loads(args['ape'].read_text())
    access = {'type': 'Array', 'name': 'spread[10]', 'object': 'global::spread',
              'indices': ['10'], 'elem_size': 3, 'op': 'load'}
    ape['functions'][0]['body'] = [access, access]
    args['ape'].write_text(json.dumps(ape))
    result = evaluate_task(**args)
    assert result['source_accesses'] == 2
    assert result['modeled_accesses'] == 4
    assert result['reference']['counts'] == [2, 0, 2]
    assert result['csrd']['counts'] == [2, 0, 2]


def test_actual_cpp_full_stream_llc_control_is_not_demand_hierarchy(tmp_path):
    args = arguments(tmp_path, 'spread')
    ape = json.loads(args['ape'].read_text())
    ape['functions'][0]['body'] = [
        {'type': 'Array', 'name': f'spread[{line * 32}]', 'object': 'global::spread',
         'indices': [str(line * 32)], 'op': 'load'} for line in [0, 1, 0, 2, 3, 4, 0]]
    args['ape'].write_text(json.dumps(ape))
    config = {'schema_version': 1, 'cores': {'count': 1, 'mapping': [{'id': 0, 'l1': 'L1'}]},
              'caches': [
                  {'name': 'L1', 'role': 'L1', 'private_to': 0, 'size_bytes': 64,
                   'line_size': 32, 'associativity': 1, 'replacement': 'LRU',
                   'write_policy': 'write-back', 'write_allocate': True,
                   'delay_cycles': 1, 'next': 'LLC'},
                  {'name': 'LLC', 'role': 'LLC', 'size_bytes': 128,
                   'line_size': 32, 'associativity': 4, 'replacement': 'LRU',
                   'write_policy': 'write-back', 'write_allocate': True,
                   'delay_cycles': 1, 'next': 'Memory'}],
              'memory': {'name': 'Memory', 'delay_cycles': 1}}
    args['cache'] = tmp_path / 'cache.json'
    args['cache'].write_text(json.dumps(config))
    result = evaluate_task(**args)
    assert result['reference']['counts'] == result['csrd']['counts'] == [1, 0, 6]
    assert result['global_rd']['counts'] == [1, 1, 5]


def test_empty_input_has_no_accuracy_metric(tmp_path):
    args = arguments(tmp_path)
    ape = json.loads(args['ape'].read_text())
    ape['functions'][0]['body'] = []
    args['ape'].write_text(json.dumps(ape))
    result = evaluate_task(**args)
    assert result['status'] == 'empty'
    assert result['reference']['counts'] == [0, 0, 0]
    assert result['reference']['ratios'] is None
    assert result['csrd']['error'] is None


def test_cli_exports_comparison_and_rejects_overwrite(tmp_path):
    args = arguments(tmp_path)
    argv = ['python3', '-m', 'tools.compare_s1', args.pop('task_id')]
    for name, value in args.items():
        argv.extend(['--' + ('output' if name == 'output_dir' else name.replace('_', '-')), str(value)])
    run = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert 'ok' in run.stdout
    original = (args['output_dir'] / 'comparison.json').read_bytes()
    run = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 2
    assert (args['output_dir'] / 'comparison.json').read_bytes() == original
