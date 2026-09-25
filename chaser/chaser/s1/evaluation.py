"""Run S1 model comparison on one caller-prepared APE and linked ELF."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from chaser.locality.cache_reference import CacheLevel, FirstHits, simulate
from chaser.locality.estimators import global_rd, compare
from chaser.locality.artifacts import read_analysis


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def _global_config(result: dict) -> dict:
    """One L1 set makes its full-exact CSRD histogram full-stream Global RD.

    The derived LLC is required by YARDA's two-level CLI but its hits are not
    used by the full-stream threshold control. Delay fields are not modeled.
    """
    levels = {level['name']: level for level in result['cache_hierarchy']['levels']}
    path = result['selected_path']
    caches = []
    for key, role in (('l1_name', 'L1'), ('llc_name', 'LLC')):
        level = levels[path[key]]
        cache = {'name': level['name'], 'role': role, 'size_bytes': level['size_bytes'],
                 'line_size': level['line_size_bytes'], 'associativity': level['associativity'],
                 'replacement': 'LRU', 'write_policy': 'write-back', 'write_allocate': True,
                 'delay_cycles': 1, 'next': path['llc_name'] if role == 'L1' else path['memory_name']}
        if role == 'L1':
            cache.update(private_to=0, associativity=level['size_bytes'] // level['line_size_bytes'])
        caches.append(cache)
    return {'schema_version': 1, 'cores': {'count': 1, 'mapping': [{'id': 0, 'l1': path['l1_name']}]},
            'caches': caches, 'memory': {'name': path['memory_name'], 'delay_cycles': 1}}


def _scored(counts: FirstHits, reference: FirstHits) -> dict:
    return {'counts': [counts.l1, counts.llc, counts.miss],
            'ratios': list(counts.ratios) if counts.ratios is not None else None,
            'error': compare(counts, reference)}


def evaluate_task(task_id: str, *, ape: Path, elf: Path, cache: Path, source: Path,
                  executable: Path, output_dir: Path, max_source_accesses: int,
                  max_line_references: int, max_cumulative_loop_iterations: int,
                  timeout: float = 60) -> dict:
    """Snapshot inputs, compare C++ estimators to independent resident-cache LRU.

    APE expansion and ELF resolution remain shared with YARDA. Source is
    provenance only; the caller owns source/APE/ELF correspondence. Full event
    exports are bounded explicitly, and raw failures/timeouts are preserved.
    Existing output directories are never overwritten.
    """
    originals = {name: path.resolve() for name, path in
                 dict(ape=ape, elf=elf, cache=cache, source=source, executable=executable).items()}
    functions = json.loads(originals['ape'].read_text())['functions']
    if len(functions) != 1 or functions[0]['function'] != task_id:
        raise ValueError('Expected one matching APE function')
    limits = {'--max-source-accesses': max_source_accesses,
              '--max-line-references': max_line_references,
              '--max-cumulative-loop-iterations': max_cumulative_loop_iterations}
    if any(type(n) is not int or n < 1 for n in limits.values()):
        raise ValueError('Positive integer analysis limits are required')
    if type(timeout) not in (int, float) or not isfinite(timeout) or timeout <= 0:
        raise ValueError('Positive finite timeout is required')
    hashes = {name: _hash(path) for name, path in originals.items()}
    output_dir = output_dir.resolve()
    output_dir.mkdir()
    runs, snapshot = [], {}
    phase = 'snapshot'
    try:
        for name, filename in (('ape', 'input.ape.json'), ('elf', 'input.elf'),
                               ('cache', 'input.cache.yaml'), ('source', 'input.source')):
            snapshot[name] = output_dir / filename
            shutil.copyfile(originals[name], snapshot[name])
            if _hash(snapshot[name]) != hashes[name]:
                raise ValueError('Input changed while snapshotting')
        _write(output_dir / 'inputs.json', {
            'task_id': task_id, 'original_paths': {k: str(v) for k, v in originals.items()},
            'sha256': hashes, 'limits': limits, 'timeout_seconds': timeout,
            'source_correspondence': 'caller-responsibility'})

        def run(name, config):
            output, events = output_dir / f'{name}.json', output_dir / f'{name}.events.json'
            expected = {'map_sha256': hashes['ape'], 'elf_sha256': hashes['elf'],
                        'cache_config_sha256': _hash(config)}
            argv = [str(originals['executable']), str(snapshot['ape']), '--analysis', 'hierarchy-rd',
                    '--elf', str(snapshot['elf']), '--cache', str(config), '--export', str(output),
                    '--export-events', str(events), '--event-limit', str(max_line_references)]
            for flag, value in limits.items():
                argv.extend((flag, str(value)))
            record = {'name': name, 'argv': argv, 'started_at': datetime.now(timezone.utc).isoformat()}
            runs.append(record)
            start = perf_counter()
            try:
                with (output_dir / f'{name}.log').open('w') as log:
                    process = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                record['returncode'] = process.returncode
                process.check_returncode()
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                raise
            finally:
                record['wall_seconds'] = perf_counter() - start
            record['result_sha256'], record['events_sha256'] = _hash(output), _hash(events)
            result = json.loads(output.read_text())
            analysis = read_analysis(result, json.loads(events.read_text()), task_id, expected)
            if _hash(config) != expected['cache_config_sha256']:
                raise ValueError('Cache config changed during execution')
            return result, analysis

        phase = 'actual'
        actual_result, actual = run('actual', snapshot['cache'])
        phase = 'global'
        derived = output_dir / 'global.cache.json'
        _write(derived, _global_config(actual_result))
        global_result, global_analysis = run('global', derived)
        if global_result['tool_version'] != actual_result['tool_version']:
            raise ValueError('Analyzer version changed between runs')
        if (global_analysis.l1 != CacheLevel(actual.l1.size_bytes, actual.l1.line_bytes, actual.l1.lines)
                or global_analysis.llc != actual.llc):
            raise ValueError('Derived Global RD geometry mismatch')
        if (actual.stream_hash != global_analysis.stream_hash or
                actual.task['source_accesses'] != global_analysis.task['source_accesses']):
            raise ValueError('Actual and Global RD analyses used different linked streams')
        phase = 'compare'
        reference = simulate(actual.lines, actual.l1, actual.llc)
        profile = global_analysis.task['l1']
        global_counts = global_rd({'histogram': profile['csrd_histogram'],
                                   'cold_misses': profile['cold_misses']}, actual.l1, actual.llc)
        if (any(_hash(path) != hashes[name] for name, path in originals.items()) or
                any(_hash(path) != hashes[name] for name, path in snapshot.items())):
            raise ValueError('Analysis inputs changed during execution')
        for record in runs:
            for suffix, key in (('.json', 'result_sha256'), ('.events.json', 'events_sha256')):
                if _hash(output_dir / (record['name'] + suffix)) != record[key]:
                    raise ValueError('Analysis artifacts changed during execution')
        if _hash(derived) != global_result['inputs']['cache_config_sha256']:
            raise ValueError('Derived cache config changed during execution')
        status = 'empty' if not reference.total else ('ok' if actual.counts == reference else 'mismatch')
        report = {'schema_version': 1, 'task_id': task_id, 'status': status,
                  'validation_scope': 'cache-decisions-on-yarda-emitted-linked-stream',
                  'execution_validation': 'not-performed',
                  'global_rd_rule': 'full-linked-stream-capacity-bins-v1',
                  'global_rd_histogram': 'global.json:tasks[0].l1.csrd_histogram',
                  'reference_model': 'cold-lru-all-demand-l1-misses-only-independent-levels-v1',
                  'clp_order': ['L1', 'LLC', 'memory'], 'source_accesses': actual.task['source_accesses'],
                  'modeled_accesses': reference.total, 'stream_sha256': actual.stream_hash,
                  'reference': _scored(reference, reference), 'csrd': _scored(actual.counts, reference),
                  'global_rd': _scored(global_counts, reference), 'runs': runs,
                  'cache_hierarchy': actual_result['cache_hierarchy'], 'input_sha256': hashes,
                  'tool_version': actual_result['tool_version'],
                  'implementation_sha256': {
                      name: _hash(Path(__file__).resolve().parents[1] / name) for name in
                      ('s1/evaluation.py', 'locality/artifacts.py',
                       'locality/estimators.py', 'locality/cache_reference.py')},
                  'analysis_ids': [actual_result['analysis_id'], global_result['analysis_id']]}
        _write(output_dir / 'comparison.json', report)
        return report
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        _write(output_dir / 'failure.json', {'status': 'failed', 'phase': phase,
                                           'error_type': type(error).__name__, 'error': str(error),
                                           'runs': runs, 'input_sha256': hashes})
        raise
