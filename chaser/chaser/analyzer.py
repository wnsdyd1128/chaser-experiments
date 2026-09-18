"""Run C++ locality analysis for one prepared task and preserve its provenance."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from time import perf_counter

from chaser.ca import ca_from_histogram, ca_csrd
from chaser.cls import DEFAULT_ALPHAS, cls


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def analyze_task(task_id: str, *, ape: Path, elf: Path, cache: Path, source: Path,
                 executable: Path, output_dir: Path,
                 max_cumulative_loop_iterations: int, max_source_accesses: int) -> dict:
    """Analyze a single-function APE using element, line-control and hierarchy modes.

    Compilation/APE extraction belongs to the caller. Limits are explicit so
    unsupported or oversized tasks fail visibly. A new output directory keeps
    raw exports and logs; analysis.json is written only after successful checks.
    Source hash identifies the supplied source, not a proof of build provenance.
    """
    ape, elf, cache, source, executable = [p.resolve() for p in
                                           (ape, elf, cache, source, executable)]
    functions = json.loads(ape.read_text())['functions']
    if len(functions) != 1 or functions[0]['function'] != task_id:
        raise ValueError('Expected exactly one matching APE function')
    if any(type(n) is not int or n < 1 for n in
           (max_cumulative_loop_iterations, max_source_accesses)):
        raise ValueError('Positive analyzer limits are required')
    # YARDA's wire schema names the APE input hash map_sha256.
    inputs = {'map_sha256': _hash(ape), 'elf_sha256': _hash(elf),
              'cache_config_sha256': _hash(cache)}
    source_hash, binary_hash = _hash(source), _hash(executable)
    output_dir = output_dir.resolve()
    output_dir.mkdir()
    modes = {
        'element': ['--mode', 'unroll', '--granularity', 'element',
                    '--max-cumulative-loop-iterations', str(max_cumulative_loop_iterations)],
        'line': ['--mode', 'unroll', '--granularity', 'cache-line', '--cache', str(cache),
                 '--max-cumulative-loop-iterations', str(max_cumulative_loop_iterations)],
        'hierarchy': ['--analysis', 'hierarchy-rd', '--elf', str(elf), '--cache', str(cache),
                      '--max-source-accesses', str(max_source_accesses)],
    }
    results, runs = {}, []
    for name, flags in modes.items():
        output = output_dir / (name + '.json')
        argv = [str(executable), str(ape), *flags, '--export', str(output)]
        started_at = datetime.now(timezone.utc).isoformat()
        start = perf_counter()
        with (output_dir / (name + '.log')).open('w') as log:
            subprocess.run(argv, check=True, stdout=log, stderr=subprocess.STDOUT)
        runs.append({'mode': name, 'argv': argv, 'started_at': started_at,
                     'wall_seconds': perf_counter() - start, 'output_hash': _hash(output)})
        results[name] = json.loads(output.read_text())
    result = results['hierarchy']
    if any(result['inputs'][k] != v for k, v in inputs.items()):
        raise ValueError('Analyzer result input hashes do not match')
    if (inputs != {'map_sha256': _hash(ape), 'elf_sha256': _hash(elf),
                   'cache_config_sha256': _hash(cache)} or _hash(source) != source_hash
            or _hash(executable) != binary_hash):
        raise ValueError('Analysis inputs changed during execution')
    if len(result['tasks']) != 1 or result['tasks'][0]['task_id'] != task_id:
        raise ValueError('Expected exactly one matching result task')
    task = result['tasks'][0]
    levels = {level['name']: level for level in result['cache_hierarchy']['levels']}
    path = result['selected_path']
    capacities = {'l1_capacity': levels[path['l1_name']]['size_bytes'],
                  'llc_capacity': levels[path['llc_name']]['size_bytes']}
    revision = re.search(r'git\.([0-9a-f]{40}(?:-dirty)?)', result['tool_version'])
    if revision is None:
        raise ValueError('Analyzer result must identify its revision')
    case = {'ca_caas_element': ca_from_histogram(results['element']['program']['histogram']),
            'ca_global_line': ca_from_histogram(results['line']['program']['histogram']),
            'ca_csrd_l1': ca_csrd(task), 'modeled_accesses': task['modeled_accesses'],
            'clp': [task[k] for k in ('l1_first_hit_ratio', 'llc_first_hit_ratio',
                                     'all_cache_miss_ratio')],
            'cls': {str(a): cls(task, capacities, a) for a in DEFAULT_ALPHAS}}
    provenance = {key: result[key] for key in
                  ('tool_version', 'model_id', 'inputs', 'selected_path',
                   'cache_hierarchy', 'analysis_id')}
    provenance.update(source_hash=source_hash, elf_hash=inputs['elf_sha256'],
                      ape_hash=inputs['map_sha256'], analyzer_commit=revision.group(1),
                      analyzer_binary_hash=binary_hash, cache_model_id=result['model_id'],
                      cache_config_hash=inputs['cache_config_sha256'], model_hash=None, runs=runs)
    record = {'schema_version': 1, 'task_id': task_id, 'case': case, 'provenance': provenance}
    (output_dir / 'analysis.json').write_text(
        json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + '\n')
    return record
