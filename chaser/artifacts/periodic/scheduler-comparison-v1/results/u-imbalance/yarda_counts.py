"""Per-task YARDA hierarchy counts, CLS and IR instruction counts of a prepared workload.

One clang/opt MAP extraction per prepared directory, then one combined
`hierarchy-rd` + `ir-instructions` analysis per task against the P executable
(cold task-local job, as in the CLS-distribution study). No event stream is
exported; instead the modeled access count must equal the designed job loads.
Run with PYTHONPATH set to the code copy whose rtems/baseline/build/yarda holds
the analyzer.
"""

import json
from pathlib import Path
import re
import subprocess

from chaser.locality.cls import cls
from chaser.periodic.build import YARDA
from chaser.periodic.patterns import job_access_count, loop_iterations
from tools.rtems_smoke import file_hash

ALPHA = 0.5


def extract(prepared: Path, output: Path) -> dict:
    """Write output/workload_ape.json from the prepared source; return the MAP."""
    output.mkdir(parents=True, exist_ok=True)
    source = prepared / 'source/workload.c'
    subprocess.run(['clang-14', '-O0', '-Xclang', '-disable-O0-optnone', '-g', '-emit-llvm', '-S',
                    f'-I{source.parent}', str(source), '-o', str(output / 'workload.ll')],
                   check=True, capture_output=True)
    subprocess.run(['opt-14', f'-load-pass-plugin={YARDA / "libMemoryAccessPatterns.so"}',
                    '-passes=function(mem2reg),loop-simplify,loop-annotated-trace',
                    'workload.ll', '-o', '/dev/null'], check=True, capture_output=True, cwd=output)
    return json.loads((output / 'workload_ape.json').read_text())


def analyze_task(prepared: Path, output: Path, raw: dict, task: dict) -> dict:
    """Return designed/modeled counts, CLS (alpha 0.5) and IR totals for one task."""
    task_id = task['task_id']
    functions = [f for f in raw['functions'] if f['function'] in ('task_job_' + task_id, 'kernel_' + task_id)]
    if len(functions) != 2:
        raise ValueError(f'{task_id}: expected the job wrapper and inline kernel')
    ape = output / f'{task_id}.ape.json'
    ape.write_text(json.dumps({**raw, 'functions': functions}))
    accesses, limit = job_access_count(task), loop_iterations(task) + 10
    result_path = output / f'{task_id}.json'
    subprocess.run([str(YARDA / 'backend/yarda_cpp'), str(ape), '--analysis', 'hierarchy-rd',
                    '--analysis', 'ir-instructions', '--cache', str(prepared / 'cache.yaml'),
                    '--elf', str(prepared / 'build/p.exe'), '--max-source-accesses', str(accesses),
                    '--max-line-references', str(accesses), '--max-single-loop-iterations', str(limit),
                    '--max-cumulative-loop-iterations', str(limit), '--export', str(result_path)],
                   check=True, capture_output=True)
    result = json.loads(result_path.read_text())
    entry = next(t for t in result['tasks'] if t['task_id'] == 'task_job_' + task_id)
    if (entry['modeled_accesses'] != accesses or not entry['coverage']['complete']
            or not entry['invariants']['all_passed']):
        raise ValueError(f'{task_id}: YARDA stream differs from the designed {accesses} loads')
    ir = result['ir_instructions']
    if ir['status'] != 'exact' or ir['total']['opcodes']['load']['dynamic'] != accesses:
        raise ValueError(f'{task_id}: IR count is not exact or its loads differ from the design')
    levels = {level['role']: level['size_bytes'] for level in result['cache_hierarchy']['levels']}
    revision = re.search(r'git\.([0-9a-f]{40}(?:-dirty)?)', result['tool_version'])
    return dict(accesses=accesses, l1_hits=entry['l1_first_hit_count'],
                llc_hits=entry['llc_first_hit_count'], memory=entry['all_cache_miss_count'],
                l1_misses=entry['l1']['misses'],
                cls=cls(entry, dict(l1_capacity=levels['L1'], llc_capacity=levels['LLC']), ALPHA),
                ir_instructions=ir['total']['dynamic_instructions'],
                analyzer_commit=revision.group(1) if revision else None,
                map_sha256=file_hash(ape))


def analyze(prepared: Path, output: Path) -> dict:
    """Analyze every task of a prepared workload; return task_id -> counts."""
    plan = json.loads((prepared / 'p/plan.json').read_text())
    raw = extract(prepared, output)
    return {task['task_id']: analyze_task(prepared, output, raw, task) for task in plan['tasks']}
